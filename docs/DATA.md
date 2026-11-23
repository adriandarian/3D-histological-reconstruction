# Pancreas serial sections

The real-data example uses every image in the **10x Pancreas** folder of Bijoyeta Roy's *Serial Section Histopathology Image Dataset*, version 1 (2023). Contributors include Mousumi Gupta, Bidyut Goswami and Sikkim Manipal Institute of Technology–Majitar. The source images are available under Creative Commons Attribution 4.0 International. [Dataset and attribution](https://doi.org/10.17632/fzskwpzs5j.1) · [License](https://creativecommons.org/licenses/by/4.0/)

From the project root, with the Python dependencies installed, run

```shell
python scripts/download_real.py
python -m pipeline --input data/real --output public/data/real --name "Pancreas 10x" --attribution "Bijoyeta Roy; contributors M. Gupta and B. Goswami. Mendeley Data v1 (2023), doi:10.17632/fzskwpzs5j.1, CC BY 4.0. Downsampled and registered."
```

The download requires about 110 MB. It checks the publisher's SHA-256 digest for each TIFF, including existing copies. The pipeline reads section numbers 1 through 36 from the leading filename field. All 36 source images decode as RGB at 1280 × 960 pixels. The untouched TIFFs stay in `data/real/`. Exported previews, registration transforms and masked textures are derived material.

The numeric labels give a reproducible order. The publication does not establish the cut-to-cut interval or whether tissue was lost between retained sections. All TIFF X/Y resolution tags are zero. Use pixels and section indices for this dataset. The 3D display cannot support physical distance or volume measurements.

## Registration review at 640 × 480

The baseline accepted a local translation on 11 of 35 adjacent pairs. The other 24 retained the transform of their neighbor toward the middle reference section. Mean grayscale normalized cross-correlation on the evaluated overlap increased from 0.218 to 0.259.

The red/cyan overlays for pairs 1/2, 4/5, 8/9, 12/13, 16/17, 19/20, 23/24, 27/28, 31/32 and 35/36 show residual differences throughout the series. In particular, 8/9, 12/13, 19/20 and 31/32 retain large colored regions at tissue margins. Inspect individual pairs before interpreting continuity. Cropping at the edges of translated sections is recorded in the validity mask.

[Three exploratory landmark correspondences](pancreas_landmarks.csv) were marked visually in the original previews. Coordinates are in the 640 × 480 source frame, and section numbers start at one. On pairs 1/2, 16/17 and 35/36, the respective distances changed from 17.9 to 17.9, 148.1 to 13.9, and 35.4 to 20.9 preview pixels. The largest initial error accounts for most of the mean improvement (67.1 to 17.6 px). These approximate points cover three pairs and lack independent expert adjudication. The plan's full landmark-validation milestone remains open.
