# Summary

This is a **very** simplistic DICOM viewer for images and related segmentations (RTSTRUCT and SEG).  It was developed as a quick and dirty solution for performing spot checks on data downloaded from [The Cancer Imaging Archive](https://www.cancerimagingarchive.net/) using [tcia_utils](https://pypi.org/project/tcia-utils/).  It was later separated into a stand-alone PyPI package as many users of tcia_utils are not concerned with interactively viewing images and this capability introduced a lot of additional dependencies.  There are many other more advanced viewers out there (e.g. 3D Slicer or itkWidgets) that you should try if your data fails with this tool.

Examples for using it can be found in [demo.ipynb](https://github.com/kirbyju/simpleDicomViewer/blob/main/demo.ipynb).

This repository includes sample data from The Cancer Imaging Archive in the "data" folder which you can use for testing its features.  

### Citations:

```Zhao, B., Schwartz, L. H., Kris, M. G., & Riely, G. J. (2015). Coffee-break lung CT collection with scan images reconstructed at multiple imaging parameters (Version 3) [Dataset]. The Cancer Imaging Archive. https://doi.org/10.7937/k9/tcia.2015.u1x8a5nr```

```Wee, L., Aerts, H., Kalendralis, P., & Dekker, A. (2020). RIDER Lung CT Segmentation Labels from: Decoding tumour phenotype by noninvasive imaging using a quantitative radiomics approach [Data set]. The Cancer Imaging Archive. https://doi.org/10.7937/tcia.2020.jit9grk8```

# Acknowledgements

A big thanks to [Adam Li](https://github.com/adamli98) who introduced the functionality to display the segmentation overlays.