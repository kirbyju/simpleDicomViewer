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

try:
    # Try to import pydicom_seg
    import pydicom_seg
except ImportError:
    # If the import fails, install the forked package from GitHub with updated jsonschema version
    print(f"Installing pydicom-seg dependency. This may take a minute...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "git+https://github.com/kirbyju/pydicom-seg.git@master"])

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
    SEG_data = pydicom.dcmread(SEGPath)
    try:
        reader = pydicom_seg.MultiClassReader()
        result = reader.read(SEG_data)
    except ValueError:
        reader = pydicom_seg.SegmentReader()
        result = reader.read(SEG_data)

    if slices[0].SeriesInstanceUID != result.referenced_series_uid:
        raise Exception("The selected reference series and the annotation series don't match!")

    colorPaleatte = ["blue", "orange", "green", "red", "cyan", "brown", "lime", "purple", "yellow", "pink", "olive"] 
    def seg_animation(suppress_warnings, x, **kwargs):
        plt.imshow(pixel_data[x], cmap = plt.cm.gray)
        if isinstance(reader, pydicom_seg.reader.MultiClassReader):
            if kwargs[list(kwargs)[0]] == True:
                mask_data = result.data
                try:
                    plt.imshow(mask_data[x], cmap = plt.cm.rainbow, alpha = 0.5*(mask_data[x] > 0), interpolation = None)
                except IndexError:
                    if suppress_warnings == False:
                        print(f"Visualization for the segment failed. It does not have the same slice count as the reference series.")
        else:
            for i in result.available_segments:
                if i == 10 and len(result.available_segments) > 10:
                    print(f"Previewing first 10 of {len(result.available_segments)} labels. Please use a DICOM workstation such as 3D Slicer to view the full dataset.")
                if kwargs[list(kwargs)[i-1]] == True:
                    mask_data = result.segment_data(i)
                    cmap = matplotlib.colors.ListedColormap(colorPaleatte[i])
                    try:
                        plt.imshow(mask_data[x], cmap = cmap, alpha = 0.5*(mask_data[x] > 0), interpolation = None)
                    except IndexError:
                        if suppress_warnings == False:
                            print(f"Visualization for segment {list(kwargs.keys())[i-1]} failed. It does not have the same slice count as the reference series.")
        plt.axis('scaled')
        plt.show()

    if isinstance(reader, pydicom_seg.reader.MultiClassReader):
        kwargs = {"Show Segments": True}
        interact(seg_animation, suppress_warnings = False, x=(0, len(pixel_data)-1), **kwargs)
    else:
        kwargs = {f"{i+1} - {v.SegmentDescription}":True for i, v in enumerate(SEG_data.SegmentSequence[:10])}
        interact(seg_animation, suppress_warnings = False, x=(0, len(pixel_data)-1), **kwargs)


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


def viewSeriesAnnotation(seriesPath = "", annotationPath = ""):
    """
    Visualizes a Series (scan) and a related segmentation overlay (SEG or RTSTRUCT).
    Opens a Tkinter file browser to choose a folder/file if
    the required parameters are not specified.
    Note that non-axial images might not be correctly displayed.
    """

    if seriesPath == "":
        try:
            print(f"Select your image series.")
            tkinter.Tk().withdraw()
            folder_path = filedialog.askdirectory()
            seriesPath = folder_path
        except Exception as e:
            print(
                f"An error occurred: {e}"
                f"{seriesPath} is your path."
                f"Either Tkinter cannot be launched for series selection, or you're trying to load an unsupported modality."
                "\nYou can try specifying the folder path to avoid TKinter errors."
            )
            return
  
    if annotationPath == "":
        try:
            print(f"Select your annotation file.")
            tkinter.Tk().withdraw()
            file_path = filedialog.askopenfilename()
            annotationPath = file_path
        except Exception as e:
            print(
                f"An error occurred: {e}"
                f"Either Tkinter cannot be launched for series selection, or you're trying to load an unsupported modality."
                "\nYou can try specifying the folder path to avoid TKinter errors."
            )
            return

    if os.path.isdir(seriesPath) and os.path.isfile(annotationPath):
        annotationModality = pydicom.dcmread(annotationPath).Modality
        if annotationModality == "SEG":
            viewSeriesSEG(seriesPath, annotationPath)
        elif annotationModality == "RTSTRUCT":
            viewSeriesRT(seriesPath, annotationPath)
        else:
            print(f"Wrong modality for the segmentation series, please check your selection.")
    elif not os.path.isdir(seriesPath):
        print(f"{seriesPath} is not a directory.")
    else:
        print(f"{annotationPath} is not a file with the correct modality: {annotationModality}.")