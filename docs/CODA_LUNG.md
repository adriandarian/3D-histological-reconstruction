# CODA lung acquisition

The first 20 distributed lung images and the matching first-section annotation XML can be retrieved with Python 3.11 or later. This download uses about 1.61 GB of disk space.

~~~sh
python scripts/download_coda_lung.py
~~~

The files land in the Git-ignored directory `data/coda-lung`. The source inventory records the public Drive file ID, byte length, SHA-256 and OpenSlide in-plane pixel spacing for each slide. Checksums were computed from the retrieved files. The command verifies new and existing copies. All 20 NDPI files decoded at pyramid level 5 during acquisition. [File inventory](../scripts/coda_lung_sources.csv)

## Section interval and annotation coverage

The first 20 retained images run from `lungs_001.ndpi` through `lungs_039.ndpi` in increments of two. Han et al. report a nominal 10 µm interval between distributed images and approximately 0.5 µm per pixel. The scanner tags of these images give approximately 0.442 µm per level-zero pixel on each axis. Actual deformation, shrinkage and local cut-to-cut variation have not been measured. [Acquisition protocol, steps 5–6](https://doi.org/10.17504/protocols.io.q26g71rpkgwz/v1) · [Source folder](https://drive.google.com/drive/folders/1K-wY_ArVGbEhebQD4AjOeERwx6-4Fw3G)

The sample annotation folder contains XML files for sections 001, 061, 181, 241 and 299, plus section 121 in the testing subfolder. Only 001 falls inside this window. Its XML has 11 bronchiole regions and 14 vasculature regions, among other tissue classes. These supply first-plane anatomical labels. Following a specific labeled structure through 19 further planes requires new correspondence annotations. The protocol carries a Creative Commons Attribution license. The linked Drive folder provided no separate image redistribution license in the inspected listing. This repository carries retrieval metadata and code only for CODA. [Publisher annotations](https://drive.google.com/drive/folders/1JeFbOY3kVRQ0s3JwaJvKZ6_UKEfsRxNv) · [CODA methods](https://doi.org/10.1038/s41592-022-01650-9)

