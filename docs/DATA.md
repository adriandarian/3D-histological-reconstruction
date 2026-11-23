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

All 36 sections were registered to the middle section. The revised pipeline searches coarse translations over their shared field of view and refines candidate translations with rigid enhanced correlation coefficient (ECC) alignment. Candidate rotations are limited to 15 degrees per pair. Each accepted cumulative transform must preserve at least 70% of the preview field. The lowest observed coverage was 70.6%.

| Metric on the same 35 adjacent pairs | Translation baseline (938fbf3) | Rigid refinement |
| --- | ---: | ---: |
| Accepted adjacent transforms | 11 | 26 |
| Identity fallbacks | 24 | 9 |
| Mean correlation on identical valid pixels | 0.245 | 0.323 |
| Mean error on three exploratory landmarks (preview px) | 17.6 | 17.6 |

For each pair, the comparison maps both registrations into the fixed section's original frame and scores the intersection of their valid pixels. Correlation improved on 23 pairs, was unchanged within 0.00001 on 11, and decreased on pair 21/22 (0.487 to 0.418). The viewer reports each method's own overlap. To reproduce the comparison, retain the baseline export from commit 938fbf3 and run:

```sh
python scripts/compare_registration.py path/to/baseline/manifest.json public/data/real/manifest.json
python scripts/landmark_error.py public/data/real/manifest.json docs/pancreas_landmarks.csv
```

The [three existing landmark correspondences](pancreas_landmarks.csv) gave mixed results. On pairs 1/2, 16/17 and 35/36 the baseline errors were 17.9, 13.9 and 20.9 pixels. The revised errors were 20.9, 10.9 and 20.9 pixels. The unregistered mean was 67.1 pixels. These approximate points lack independent expert adjudication. Correlation was used to select transforms, so its increase alone cannot establish improved anatomical accuracy.

Visual review covered pairs 1/2, 4/5, 8/9, 12/13, 16/17, 19/20, 23/24, 27/28, 31/32 and 35/36. The overlays still show mismatched margins, notably on 8/9, 12/13 and 31/32. Edge cropping is visible on 19/20 and represented in the validity mask. An identity fallback inherits its neighbor's transform. Treat these regions as uncertain when following structures in 3D.
