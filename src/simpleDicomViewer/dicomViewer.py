# --- Imports ---
import matplotlib.pyplot as plt
from ipywidgets import interactive_output, IntSlider, Checkbox, VBox, HBox
import numpy as np
import os
import pydicom
from monai.transforms import Compose, LoadImage, EnsureChannelFirst
from monai.data import ITKReader
from rt_utils import RTStruct
from IPython.display import display
import warnings

# --- DICOM UID Constants for Modality Check ---
RTSTRUCT_UID = '1.2.840.10008.5.1.4.1.1.481.3'
SEG_UID = '1.2.840.10008.5.1.4.1.1.66.4'


def viewDicom(imgPath: str, segPath: str = None):
    """
    Creates and displays an interactive DICOM viewer in a Jupyter Notebook.

    The viewer supports 3D image series, interactive slice navigation,
    window/level adjustments, and overlays for DICOM SEG and RTSTRUCT
    annotations with toggling capabilities.

    Args:
        imgPath (str):
            Path to the directory containing the DICOM image series.
        segPath (str, optional):
            Path to the DICOM segmentation file (SEG or RTSTRUCT).
            The function will auto-detect the modality. Defaults to None.
    """

    # --- 1. Load Image Series using MONAI ---
    pixel_loader = Compose([LoadImage(reader=ITKReader(reverse_indexing=True)), EnsureChannelFirst()])
    print(f"Loading image series from '{imgPath}'...")
    try:
        image_metatensor = pixel_loader(imgPath)
        image_np = image_metatensor.numpy()[0]
        print(f"Successfully loaded image pixel data. Shape: {image_np.shape}")
    except Exception as e:
        print(f"ERROR: Could not load image series from '{imgPath}'. Exception: {e}")
        return

    # --- 2. Load and Process Segmentation (with Auto-Detection) ---
    label_map_np = np.zeros_like(image_np, dtype=np.uint8)
    segment_metadata = {}

    if segPath and os.path.exists(segPath):
        try:
            dcm_header = pydicom.dcmread(segPath, force=True, stop_before_pixels=True)
            modality = dcm_header.SOPClassUID

            if modality == SEG_UID:
                print(f"Detected DICOM SEG file. Loading...")
                seg_metatensor = pixel_loader(segPath)
                stacked_mask_np = seg_metatensor.numpy()[0]
                seg_dcm = pydicom.dcmread(segPath, force=True)
                for seg_item in seg_dcm.SegmentSequence:
                    seg_num, seg_label = seg_item.SegmentNumber, seg_item.SegmentLabel
                    segment_metadata[seg_num] = seg_label
                frame_mapping = {}
                for i, frame_item in enumerate(seg_dcm.PerFrameFunctionalGroupsSequence):
                    seg_id_item = frame_item.SegmentIdentificationSequence[0]
                    segment_number = seg_id_item.ReferencedSegmentNumber
                    if segment_number not in frame_mapping: frame_mapping[segment_number] = []
                    frame_mapping[segment_number].append(i)
                for segment_number, frame_indices in frame_mapping.items():
                    segment_mask = stacked_mask_np[frame_indices] > 0
                    label_map_np[segment_mask] = segment_number
                print("Successfully created label map from DICOM SEG.")

            elif modality == RTSTRUCT_UID:
                print(f"Detected DICOM RTSTRUCT file. Loading...")
                print("Loading and sorting source DICOM series for RTSTRUCT alignment...")
                dicom_series_paths = [os.path.join(imgPath, f) for f in os.listdir(imgPath) if f.endswith('.dcm')]
                series_data = [pydicom.dcmread(p, force=True) for p in dicom_series_paths]
                series_data.sort(key=lambda x: float(x.SliceLocation))
                rtstruct_dcm = pydicom.dcmread(segPath, force=True)
                rtstruct = RTStruct(series_data, rtstruct_dcm)
                roi_names = rtstruct.get_roi_names()
                print(f"Found {len(roi_names)} ROIs: {roi_names}")
                for i, roi_name in enumerate(roi_names):
                    segment_number = i + 1
                    segment_metadata[segment_number] = roi_name
                    mask_3d = rtstruct.get_roi_mask_by_name(roi_name)
                    if mask_3d.shape != label_map_np.shape:
                        mask_3d = mask_3d.transpose(2, 0, 1)
                    label_map_np[mask_3d] = segment_number
                print("Successfully created label map from RTSTRUCT.")

            else:
                print(f"Warning: Unsupported segmentation modality UID: {modality}")

        except Exception as e:
            print(f"ERROR: Could not process segmentation file '{segPath}'. Exception: {e}")
            pass
    else:
        print("No segmentation file found. Viewer will show image only.")

    # --- 3. Create Stable Color Map and Widgets ---
    color_map = {}
    if segment_metadata:
        max_seg_num = max(segment_metadata.keys())
        cmap = plt.get_cmap('gist_rainbow', max_seg_num + 1)
        for seg_num, seg_label in segment_metadata.items():
            color_map[seg_num] = cmap(seg_num / max_seg_num)

    data_min, data_max = image_np.min(), image_np.max()
    default_width = int(data_max - data_min)
    default_level = int(data_min + default_width / 2)

    controls = {
        'slice_index': IntSlider(min=0, max=image_np.shape[0] - 1, step=1, value=image_np.shape[0] // 2, description="Slice", continuous_update=False, layout={'width': '400px'}),
        'window_level': IntSlider(min=data_min, max=data_max, step=1, value=default_level, description="Level", continuous_update=False, layout={'width': '400px'}),
        'window_width': IntSlider(min=1, max=default_width, step=1, value=default_width, description="Width", continuous_update=False, layout={'width': '400px'}),
    }
    roi_checkboxes = []
    for seg_num, seg_label in segment_metadata.items():
        controls[f'show_{seg_label}'] = Checkbox(value=True, description=seg_label)
        roi_checkboxes.append(controls[f'show_{seg_label}'])

    # --- 4. Define the Plotting Function ---
    def plot_slice_with_overlays(slice_index, window_level, window_width, **kwargs):
        image_slice = image_np[slice_index, :, :]
        lower_bound = window_level - (window_width / 2)
        upper_bound = window_level + (window_width / 2)
        windowed_slice = np.clip(image_slice, lower_bound, upper_bound)
        norm_image_slice = (windowed_slice - lower_bound) / (window_width + 1e-6)
        rgb_image_slice = np.stack([norm_image_slice]*3, axis=-1)
        overlay_slice = np.zeros_like(rgb_image_slice)
        for seg_num, seg_label in segment_metadata.items():
            if kwargs.get(f'show_{seg_label}', False):
                mask = label_map_np[slice_index, :, :] == seg_num
                overlay_slice[mask] = color_map[seg_num][:3]
        active_pixels = overlay_slice.sum(axis=2) > 0
        alpha = 0.6
        rgb_image_slice[active_pixels] = (rgb_image_slice[active_pixels] * (1 - alpha) + overlay_slice[active_pixels] * alpha)

        fig, ax = plt.subplots(figsize=(10, 10))
        ax.imshow(rgb_image_slice)
        ax.set_title(f"Slice {slice_index + 1} / {image_np.shape[0]}")
        ax.axis('off')
        plt.show()

    # --- 5. Set Up the Interactive Viewer Layout ---
    print("\nInitializing interactive viewer...")
    ui_panel = VBox([controls['slice_index'], controls['window_level'], controls['window_width'], VBox(roi_checkboxes)])
    output_panel = interactive_output(plot_slice_with_overlays, controls)
    display(HBox([ui_panel, output_panel]))


# --- Backward Compatibility Wrappers ---

def viewSeriesAnnotation(seriesPath: str, annotationPath: str):
    """
    DEPRECATED: This function is deprecated and will be removed in a future version.
    Please use viewDicom() instead.

    Calls viewDicom(imgPath=seriesPath, segPath=annotationPath).
    """
    warnings.warn(
        "`viewSeriesAnnotation()` is deprecated and will be removed in a future version. "
        "Use `viewDicom()` instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return viewDicom(imgPath=seriesPath, segPath=annotationPath)


def viewSeries(seriesPath: str):
    """
    DEPRECATED: This function is deprecated and will be removed in a future version.
    Please use viewDicom() instead.

    Calls viewDicom(imgPath=seriesPath, segPath=None).
    """
    warnings.warn(
        "`viewSeries()` is deprecated and will be removed in a future version. "
        "Use `viewDicom()` instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return viewDicom(imgPath=seriesPath, segPath=None)
