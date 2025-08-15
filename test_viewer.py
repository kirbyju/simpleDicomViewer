import sys
from unittest.mock import patch, MagicMock

# Mock pydicom_seg before it's imported by simpleDicomViewer
mock_pydicom_seg = MagicMock()
sys.modules['pydicom_seg'] = mock_pydicom_seg

# Mock tkinter
mock_tkinter = MagicMock()
sys.modules['tkinter'] = mock_tkinter
sys.modules['tkinter.filedialog'] = mock_tkinter.filedialog

from simpleDicomViewer import dicomViewer
import pydicom
import numpy as np

# --- Mocks for pydicom and related objects ---

# Mock Slice
mock_slice = pydicom.dataset.Dataset()
mock_slice.InstanceNumber = 1
mock_slice.Modality = 'CT'
mock_slice.RescaleIntercept = -1024
mock_slice.RescaleSlope = 1
# Mock file meta
file_meta = pydicom.dataset.FileMetaDataset()
mock_slice.PixelData = np.zeros((5, 5), dtype=np.uint16).tobytes()
mock_slice.SeriesInstanceUID = '1.2.3'
mock_slice.file_meta = file_meta
mock_slice.BitsAllocated = 16
mock_slice.Rows = 5
mock_slice.Columns = 5
mock_slice.SamplesPerPixel = 1
mock_slice.PhotometricInterpretation = "MONOCHROME2"
mock_slice.PixelRepresentation = 1
mock_slice.BitsStored = 16
file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.66.4' # Segmentation Storage
file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian

# Mock SEG Data
mock_seg_data = pydicom.dataset.Dataset()
mock_seg_data.Modality = 'SEG'
mock_seg_data.file_meta = file_meta
mock_seg_data.BitsAllocated = 16
mock_seg_data.Rows = 5
mock_seg_data.Columns = 5
mock_seg_data.SamplesPerPixel = 1
mock_seg_data.PhotometricInterpretation = "MONOCHROME2"
mock_seg_data.PixelRepresentation = 1
mock_seg_data.BitsStored = 16

# Mock pydicom_seg Reader
mock_reader_instance = MagicMock()
mock_reader_instance.read.return_value = MagicMock(
    referenced_series_uid='1.2.3',
    available_segments=[1],
    data=np.ones((1, 5, 5))  # One slice, 5x5
)
mock_pydicom_seg.MultiClassReader.return_value = mock_reader_instance

# --- Test Function ---

@patch('pydicom.dcmread')
@patch('os.listdir')
@patch('os.path.isfile')
@patch('os.path.isdir')
@patch('matplotlib.pyplot.show')
def test_viewSeriesSEG_runs(mock_show, mock_isdir, mock_isfile, mock_listdir, mock_dcmread):
    """
    Tests that viewSeriesSEG runs without error.
    """
    mock_isdir.return_value = True
    mock_isfile.return_value = True
    mock_listdir.return_value = ['1.dcm']
    mock_dcmread.side_effect = [mock_seg_data, mock_slice, mock_seg_data]

    try:
        dicomViewer.viewSeriesAnnotation(seriesPath='fake/series', annotationPath='fake/seg')
    except Exception as e:
        assert False, f"viewSeriesAnnotation raised an exception: {e}"

print("Running test...")
# We need to manually call the test function as we are not using a test runner
test_viewSeriesSEG_runs()
print("Test finished.")
