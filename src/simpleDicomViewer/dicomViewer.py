# --- Imports ---
import matplotlib.pyplot as plt
from ipywidgets import interactive_output, IntSlider, Checkbox, VBox, HBox, Dropdown
import numpy as np
import os
import pydicom
from rt_utils import RTStruct
from IPython.display import display
import warnings
import glob

# --- DICOM UID Constants ---
RTSTRUCT_UID = '1.2.840.10008.5.1.4.1.1.481.3'
SEG_UID = '1.2.840.10008.5.1.4.1.1.66.4'

def viewDicom(imgPath: str, segPath: str = None):
    """
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

    # --- 1. Load Image Series using the Official pydicom Method ---
    print(f"Loading image series from '{imgPath}'...")
    try:
        dicom_files = glob.glob(os.path.join(imgPath, '*'))
        slices = [pydicom.dcmread(f, force=True) for f in dicom_files]
        image_slices = [s for s in slices if hasattr(s, 'SliceLocation')]
        image_slices.sort(key=lambda x: float(x.SliceLocation))

        # Apply Rescale Slope and Intercept
        # This converts the raw pixel values to Hounsfield Units (HU)
        pixel_arrays = []
        for s in image_slices:
            # Get slope and intercept, defaulting to 1 and 0 if not present
            slope = float(getattr(s, 'RescaleSlope', 1))
            intercept = float(getattr(s, 'RescaleIntercept', 0))

            # Apply the conversion and ensure the data type is float
            hu_pixels = s.pixel_array.astype(np.float64) * slope + intercept
            pixel_arrays.append(hu_pixels)

        image_3d_ycx = np.stack(pixel_arrays, axis=-1)

        image_np = image_3d_ycx.transpose(2, 0, 1)
        print(f"Successfully loaded and converted image to HU. Shape: {image_np.shape}")

    except Exception as e:
        print(f"ERROR: Could not load image series from '{imgPath}'. Exception: {e}")
        return

    # --- 2. Load and Process Segmentation ---
    label_map_np = np.zeros_like(image_np, dtype=np.uint8)
    segment_metadata = {}
    if segPath and os.path.exists(segPath):
        try:
            dcm_header = pydicom.dcmread(segPath, force=True, stop_before_pixels=True)
            modality = dcm_header.SOPClassUID
            if modality == SEG_UID:
                print(f"Detected DICOM SEG file. Loading...")
                seg_dcm = pydicom.dcmread(segPath, force=True)
                stacked_mask_np = seg_dcm.pixel_array
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
                # We can reuse the sorted image_slices we already loaded
                rtstruct_dcm = pydicom.dcmread(segPath, force=True)
                rtstruct = RTStruct(image_slices, rtstruct_dcm)
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

    # --- 3. Create Stable Color Map, Presets, and Widgets ---
    color_map = {}
    if segment_metadata:
        max_seg_num = max(segment_metadata.keys())
        cmap = plt.get_cmap('gist_rainbow', max_seg_num + 1)
        for seg_num, seg_label in segment_metadata.items():
            color_map[seg_num] = cmap(seg_num / max_seg_num)
    data_min, data_max = image_np.min(), image_np.max()
    presets = {
        'Default': (int(data_max - data_min), int(data_min + (data_max - data_min) / 2)),
        'Abdomen/Soft Tissue': (400, 50), 'Brain': (80, 40), 'Bone': (2000, 600),
        'Lung': (1500, -600), 'Mediastinum': (350, 50), 'Stroke': (40, 40),
        'Subdural': (150, 70),
    }
    controls = {
        'slice_index': IntSlider(min=0, max=image_np.shape[0] - 1, value=image_np.shape[0] // 2, description="Slice", continuous_update=False, layout={'width': '400px'}),
        'window_level': IntSlider(min=data_min, max=data_max, value=presets['Default'][1], description="Level", continuous_update=False, layout={'width': '400px'}),
        'window_width': IntSlider(min=1, max=int(data_max - data_min), value=presets['Default'][0], description="Width", continuous_update=False, layout={'width': '400px'}),
        'preset_selector': Dropdown(options=list(presets.keys()), value='Default', description='Preset:', layout={'width': '400px'}),
    }
    roi_checkboxes = []
    for seg_num, seg_label in segment_metadata.items():
        controls[f'show_{seg_label}'] = Checkbox(value=True, description=seg_label)
        roi_checkboxes.append(controls[f'show_{seg_label}'])
    def update_sliders_from_preset(change):
        if change.new in presets:
            width, level = presets[change.new]
            controls['window_width'].value = width
            controls['window_level'].value = level
    controls['preset_selector'].observe(update_sliders_from_preset, names='value')

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
    ui_panel = VBox([controls['preset_selector'], controls['slice_index'], controls['window_level'], controls['window_width'], VBox(roi_checkboxes)])
    plot_controls = {k: v for k, v in controls.items() if k != 'preset_selector'}
    output_panel = interactive_output(plot_slice_with_overlays, plot_controls)
    display(HBox([ui_panel, output_panel]))

def viewSeriesAnnotation(seriesPath: str, annotationPath: str):
    warnings.warn("`viewSeriesAnnotation()` is deprecated. Use `viewDicom()` instead.", DeprecationWarning, stacklevel=2)
    viewDicom(imgPath=seriesPath, segPath=annotationPath)

def viewSeries(seriesPath: str):
    warnings.warn("`viewSeries()` is deprecated. Use `viewDicom()` instead.", DeprecationWarning, stacklevel=2)
    viewDicom(imgPath=seriesPath, segPath=None)
