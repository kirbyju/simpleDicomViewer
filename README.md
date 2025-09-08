# Summary

This is a simplistic DICOM viewer for images and related segmentations (RTSTRUCT and SEG).  It was developed as a quick and dirty solution for performing spot checks on data downloaded from [The Cancer Imaging Archive (TCIA)](https://www.cancerimagingarchive.net/) using [tcia_utils](https://pypi.org/project/tcia-utils/).  It was later separated into a stand-alone PyPI package as many users of tcia_utils are not concerned with interactively viewing images and this capability introduced a lot of additional dependencies.  There are many other more advanced viewers out there (e.g. 3D Slicer or itkWidgets) that you should try if your data fails with this tool.

[![PyPI Downloads](https://static.pepy.tech/personalized-badge/simpledicomviewer?period=month&units=international_system&left_color=blue&right_color=grey&left_text=Downloads%20/%20Month)](https://pepy.tech/project/simpledicomviewer)

# Installation

Installation is performed using `pip install simpleDicomViewer` or:

```
import sys

# install simpleDicomViewer
!{sys.executable} -m pip install --upgrade -q simpleDicomViewer
```

# Usage

For viewing images, specify the path to a directory containing images from a single DICOM series.  For annotations/segmentations, the path should point to the specific SEG or RTSTRUCT DICOM file name (not directory) that you're trying to visualize.

```
from simpleDicomViewer import dicomViewer

viewDicom(imagePath, segmentationPath)
```

Functional examples using TCIA data can be found in [TCIA_Segmentations.ipynb](https://github.com/kirbyju/TCIA_Notebooks/blob/main/TCIA_Segmentations.ipynb).

# Acknowledgements

Thanks to [Adam Li](https://github.com/adamli98) who introduced the original functionality in v1.x to display the segmentation overlays.

### Citations:
This repository includes sample data from The Cancer Imaging Archive in the "data" folder which you can use for testing its features.  

1. Zhao, B., Schwartz, L. H., Kris, M. G., & Riely, G. J. (2015). Coffee-break lung CT collection with scan images reconstructed at multiple imaging parameters (Version 3) [Dataset]. The Cancer Imaging Archive. https://doi.org/10.7937/k9/tcia.2015.u1x8a5nr
2. Wee, L., Aerts, H., Kalendralis, P., & Dekker, A. (2020). RIDER Lung CT Segmentation Labels from: Decoding tumour phenotype by noninvasive imaging using a quantitative radiomics approach [Data set]. The Cancer Imaging Archive. https://doi.org/10.7937/tcia.2020.jit9grk8
