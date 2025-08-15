from ipywidgets import interact
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pydicom
import rt_utils
import os
import subprocess
import sys

try:
    import tkinter
    from tkinter import filedialog
except ModuleNotFoundError:
    tkinter = None

import highdicom as hd

class StopExecution(Exception):
    def _render_traceback_(self):
        pass


def viewSeries(path = ""):
    """
    Visualizes a DICOM series (scan).
    If neither no path is specified, the user will be
    prompted to select a directory using a GUI.
    """
    # set path where downloadSeries() saves the data if seriesUid is provided
    if path == "":
        try:
            tkinter.Tk().withdraw()
            folder_path = filedialog.askdirectory()
            path = folder_path
        except Exception:
            print(
                f"Either Tkinter cannot be launched for series selection, or you're trying to load an unsupported modality."
                "\nYou can try specifying the folder path to avoid TKinter errors."
            )
            return

    # Verify series exists before visualizing
    if os.path.isdir(path):
        # load scan to pydicom
        slices = [pydicom.dcmread(path + '/' + s) for s in
                  os.listdir(path) if s.endswith(".dcm")]

        slices.sort(key = lambda x: int(x.InstanceNumber), reverse = True)

        try:
            modality = slices[0].Modality
        except IndexError:
            print(f"Your path does not contain a single DICOM series.")
            raise StopExecution

        image = np.stack([s.pixel_array for s in slices])
        image = image.astype(np.int16)

        if modality == "CT":
            # Set outside-of-scan pixels to 0
            # The intercept is usually -1024, so air is approximately 0
            image[image == -2000] = 0

            # Convert to Hounsfield units (HU)
            intercept = slices[0].RescaleIntercept
            slope = slices[0].RescaleSlope

            if slope != 1:
                image = slope * image.astype(np.float64)
                image = image.astype(np.int16)

            image += np.int16(intercept)

        pixel_data = np.array(image, dtype=np.int16)

        # slide through dicom images using a slide bar
        def dicom_animation(x):
            plt.imshow(pixel_data[x], cmap = plt.cm.gray)
            plt.show()
        interact(dicom_animation, x=(0, len(pixel_data)-1))
    else:
        print(f"Your path does not contain a single DICOM series.")


def viewSeriesSEG(seriesPath = "", SEGPath = ""):
    """
    Visualizes a Series (scan) and with a SEG series overlay.
    Requires a path parameter for the reference series.
    Requires the file path for the annotation series.
    Used by the viewSeriesAnnotation() function.
    Not recommended to be used as a standalone function.
    """
    slices = [pydicom.dcmread(seriesPath + '/' + s) for s in os.listdir(seriesPath) if s.endswith(".dcm")]
    slices.sort(key = lambda x: int(x.InstanceNumber), reverse = True)

    try:
        modality = slices[0].Modality
    except IndexError:
        print(f"Your path does not contain a single DICOM series.")
        raise StopExecution

    image = np.stack([s.pixel_array for s in slices])
    image = image.astype(np.int16)

    if modality == "CT":
        # Set outside-of-scan pixels to 0
        # The intercept is usually -1024, so air is approximately 0
        image[image == -2000] = 0

        # Convert to Hounsfield units (HU)
        intercept = slices[0].RescaleIntercept
        slope = slices[0].RescaleSlope

        if slope != 1:
            image = slope * image.astype(np.float64)
            image = image.astype(np.int16)

        image += np.int16(intercept)

    pixel_data = np.array(image, dtype=np.int16)

    # Use highdicom to read the SEG file
    seg = hd.seg.segread(SEGPath)

    # Verify that the segmentation references the correct series
    source_image_uids = {sop for _, _, sop in seg.get_source_image_uids()}
    slice_uids = {s.SOPInstanceUID for s in slices}
    if not source_image_uids.issubset(slice_uids):
        # This is not a perfect check, but it's a good heuristic.
        # A more robust check would involve matching frame of reference UIDs.
        print("Warning: The segmentation may not reference the correct image series.")

    colorPaleatte = ["blue", "orange", "green", "red", "cyan", "brown", "lime", "purple", "yellow", "pink", "olive"]

    # Get descriptions for all segments
    segment_descriptions = [seg.get_segment_description(i) for i in seg.get_segment_numbers()]

    def seg_animation(suppress_warnings, x, **kwargs):
        plt.imshow(pixel_data[x], cmap = plt.cm.gray)

        current_slice_uid = slices[x].SOPInstanceUID

        for i, desc in enumerate(segment_descriptions):
            if i >= 10:
                if not suppress_warnings:
                    print(f"Previewing first 10 of {len(segment_descriptions)} labels. Please use a DICOM workstation such as 3D Slicer to view the full dataset.")
                break

            kwarg_key = f"{desc.segment_number} - {desc.SegmentDescription}"
            if kwargs.get(kwarg_key, False):
                try:
                    # Get mask for the current slice and segment
                    mask_data = seg.get_pixels_by_source_instance(
                        source_sop_instance_uids=[current_slice_uid],
                        segment_numbers=[desc.segment_number]
                    )
                    # The output is (instances, rows, cols, segments), so we squeeze it
                    mask_data = np.squeeze(mask_data)

                    if mask_data.ndim == 2 and mask_data.shape == pixel_data[x].shape:
                        cmap = matplotlib.colors.ListedColormap(colorPaleatte[i % len(colorPaleatte)])
                        plt.imshow(mask_data, cmap=cmap, alpha=0.5 * (mask_data > 0), interpolation=None)
                    elif not suppress_warnings:
                        print(f"No segmentation found for segment '{desc.SegmentDescription}' on this slice.")

                except Exception as e:
                    if not suppress_warnings:
                        print(f"Could not display segment '{desc.SegmentDescription}': {e}")

        plt.axis('scaled')
        plt.show()

    kwargs = {f"{desc.segment_number} - {desc.SegmentDescription}": True for desc in segment_descriptions[:10]}
    interact(seg_animation, suppress_warnings=False, x=(0, len(pixel_data)-1), **kwargs)


def viewSeriesRT(seriesPath = "", RTPath = ""):
    """
    Visualizes a Series (scan) with an RTSTRUCT overlay.
    Requires a path parameter for the reference series.
    Requires the file path for the annotation series.
    Currenly not able to visualize seed points or fiducials.
    Used by the viewSeriesAnnotation() function.
    Not recommended to be used as a standalone function.
    """
    rtstruct = rt_utils.RTStructBuilder.create_from(seriesPath, RTPath)
    roi_names = rtstruct.get_roi_names()

    slices = rtstruct.series_data
    try:
        modality = slices[0].Modality
    except IndexError:
        print(f"Your path does not contain a single DICOM series.")
        raise StopExecution

    image = np.stack([s.pixel_array for s in slices])
    image = image.astype(np.int16)

    if modality == "CT":
        # Set outside-of-scan pixels to 0
        # The intercept is usually -1024, so air is approximately 0
        image[image == -2000] = 0

        # Convert to Hounsfield units (HU)
        intercept = slices[0].RescaleIntercept
        slope = slices[0].RescaleSlope

        if slope != 1:
            image = slope * image.astype(np.float64)
            image = image.astype(np.int16)

        image += np.int16(intercept)

    pixel_data = np.array(image, dtype=np.int16)
    colorPaleatte = ["blue", "orange", "green", "red", "cyan", "brown", "lime", "purple", "yellow", "pink", "olive"]
    def rt_animation(suppress_warnings, x, **kwargs):
        plt.imshow(pixel_data[x], cmap = plt.cm.gray, interpolation = None)
        for i in range(len(kwargs)):
            if i == 9 and len(roi_names) > 10:
                print(f"Previewing first 10 of {len(roi_names)} labels. Please use a DICOM workstation such as 3D Slicer to view the full dataset.")
            if kwargs[f"{i+1} - {roi_names[i]}"] == True:
                try:
                    mask_data = rtstruct.get_roi_mask_by_name(roi_names[i])
                    cmap = matplotlib.colors.ListedColormap(colorPaleatte[i])
                    try:
                        plt.imshow(mask_data[:, :, x], cmap = cmap, alpha = 0.5*(mask_data[:, :, x] > 0), interpolation = None)
                    except IndexError:
                        if suppress_warnings == False:
                            print(f"Visualization for segment {roi_names[i]} failed. It does not have the same slide count as the reference series.")
                except Exception as e:
                    try:
                        if e.code == -215:
                            error_message = f"\nThe segment '{roi_names[i]}' is too small to visualize."
                        else:
                            error_message = f"\nThe segment '{roi_names[i]}' is too small to visualize."
                        if suppress_warnings == False: print(error_message)
                        pass
                    except:
                        if suppress_warnings == False: print(f"\n{e}")
                        pass
        plt.axis('scaled')
        plt.show()

    kwargs = {f"{i+1} - {v}": True for i, v in enumerate(roi_names[:10])}
    interact(rt_animation, suppress_warnings = False, x = (0, len(pixel_data)-1), **kwargs)


def viewSeriesAnnotation(seriesPath="", annotationPath=""):
    """
    Visualizes a Series (scan) and a related segmentation overlay (SEG or RTSTRUCT).
    Opens a Tkinter file browser to choose a folder/file if
    the required parameters are not specified.
    Note that non-axial images might not be correctly displayed.
    """

    # Handle seriesPath selection via Tkinter if not provided
    if seriesPath == "":
        try:
            print(f"Select your image series.")
            tkinter.Tk().withdraw()
            seriesPath = filedialog.askdirectory()
        except Exception as e:
            print(
                f"An error occurred: {e}"
                "\nEither Tkinter cannot be launched for series selection, or you're trying to load an unsupported modality."
                "\nYou can try specifying the folder path to avoid TKinter errors."
            )
            return

    # Handle annotationPath selection via Tkinter if not provided
    if annotationPath == "":
        try:
            print(f"Select your annotation file.")
            tkinter.Tk().withdraw()
            annotationPath = filedialog.askopenfilename()
        except Exception as e:
            print(
                f"An error occurred: {e}"
                "\nEither Tkinter cannot be launched for annotation selection, or you're trying to load an unsupported modality."
                "\nYou can try specifying the annotation file path to avoid TKinter errors."
            )
            return

    # Check if the seriesPath is valid
    if not os.path.isdir(seriesPath):
        print(f"{seriesPath} is not a directory.")
        return

    # Check if the annotationPath is valid
    if not os.path.isfile(annotationPath):
        print(f"{annotationPath} is not a valid file path.")
        return

    # Try to read the annotation file and check the modality
    try:
        # Safely read the annotation file
        annotationModality = pydicom.dcmread(annotationPath).Modality

        # Check the modality and proceed accordingly
        if annotationModality == "SEG":
            viewSeriesSEG(seriesPath, annotationPath)
        elif annotationModality == "RTSTRUCT":
            viewSeriesRT(seriesPath, annotationPath)
        else:
            print(f"Wrong modality for the segmentation series, please check your selection.")
    except Exception as e:
        print(f"Error reading DICOM file {annotationPath}: {e}")
