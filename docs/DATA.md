# Pancreas serial sections

The real-data example uses every image in the **10x Pancreas** folder of Bijoyeta Roy's *Serial Section Histopathology Image Dataset*, version 1 (2023). Contributors include Mousumi Gupta, Bidyut Goswami and Sikkim Manipal Institute of Technology–Majitar. The source images are available under Creative Commons Attribution 4.0 International. [Dataset and attribution](https://doi.org/10.17632/fzskwpzs5j.1) · [License](https://creativecommons.org/licenses/by/4.0/)

From the project root, with the Python dependencies installed, run

```shell
python scripts/download_real.py
python -m pipeline --input data/real --output public/data/real --local-refinement he-contour --name "Pancreas 10x" --attribution "Bijoyeta Roy; contributors M. Gupta and B. Goswami. Mendeley Data v1 (2023), doi:10.17632/fzskwpzs5j.1, CC BY 4.0. Downsampled and registered."
```

The download requires about 110 MB. It checks the publisher's SHA-256 digest for each TIFF, including existing copies. The pipeline reads section numbers 1 through 36 from the leading filename field. All 36 source images decode as RGB at 1280 × 960 pixels. The untouched TIFFs stay in `data/real/`. Exported previews, registration transforms and masked textures are derived material.

The numeric labels give a reproducible order. The publication does not establish the cut-to-cut interval or whether tissue was lost between retained sections. All TIFF X/Y resolution tags are zero. Use pixels and section indices for this dataset. The 3D display cannot support physical distance or volume measurements.

## Rigid registration review at 640 × 480

All 36 sections were registered to the middle section. The revised pipeline searches coarse translations over their shared field of view and refines candidate translations with rigid enhanced correlation coefficient (ECC) alignment. Candidate rotations are limited to 15 degrees per pair. Each accepted cumulative transform must preserve at least 70% of the preview field. The lowest observed coverage was 70.6%.

| Metric on the same 35 adjacent pairs | Translation baseline (938fbf3) | Rigid refinement |
| --- | ---: | ---: |
| Accepted adjacent transforms | 11 | 26 |
| Identity fallbacks | 24 | 9 |
| Mean correlation on identical valid pixels | 0.245 | 0.323 |
| Mean error on three exploratory landmarks (preview px) | 17.6 | 17.6 |

For each pair, the comparison maps both registrations into the fixed section's original frame and scores the intersection of their valid pixels. Correlation improved on 23 pairs, was unchanged within 0.00001 on 11, and decreased on pair 21/22 (0.487 to 0.418). The viewer reports each method's own overlap. To reproduce the comparison, retain the baseline export from commit 938fbf3 and run:

```sh
python scripts/compare_registration.py path/to/baseline/manifest.json path/to/rigid/manifest.json
python scripts/landmark_error.py path/to/rigid/manifest.json docs/pancreas_landmarks.csv
```

The [three existing landmark correspondences](pancreas_landmarks.csv) gave mixed results. On pairs 1/2, 16/17 and 35/36 the baseline errors were 17.9, 13.9 and 20.9 pixels. The revised errors were 20.9, 10.9 and 20.9 pixels. The unregistered mean was 67.1 pixels. These approximate points lack independent expert adjudication. Correlation was used to select transforms, so its increase alone cannot establish improved anatomical accuracy.

Visual review covered pairs 1/2, 4/5, 8/9, 12/13, 16/17, 19/20, 23/24, 27/28, 31/32 and 35/36. The overlays still show mismatched margins, notably on 8/9, 12/13 and 31/32. Edge cropping is visible on 19/20 and represented in the validity mask. An identity fallback inherits its neighbor's transform. Treat these regions as uncertain when following structures in 3D.

## Local refinement and landmark review

The documented pancreas command adds an image-only correction after rigid registration. Forward and backward optical flow estimate local motion between adjacent sections. The solver smooths reliable correspondences onto a sparse grid and limits deformation to keep the mapping invertible. The reference plane and adjacent rigid pairs with correlation above 0.98 retain their rigid transforms.

All local modes use the rigid frame and its validity masks. The earlier intensity mode estimates flow from grayscale previews. The H&E mode estimates broad shifts by dense inverse search on the red channel and smaller shifts by a 17-pixel Farneback window on the green channel. Each estimate is weighted spatially by forward/backward consistency, then normalized. The solver combines the two displacements with a 2:1 weight on the broad estimate. The channel, estimator and weight were selected by comparing results on this series.

The `he-contour` mode starts from the H&E export and detects protruding tissue tips along bright glass connected to the valid image boundary. Two passes match 73-by-73 grayscale patches in both directions between nearby, mutually nearest tips. Each accepted match adjusts the pull grid locally. The reference and zero-displacement planes stay fixed. Each update must preserve the displacement-gradient bound and at least 70% valid field. Each pass resamples the original section.

The eight manual correspondences span four adjacent pairs. The coordinates are unchanged and the pipeline reads images alone. All eight were available during method selection, so these are development measurements. Errors are Euclidean distances in the registered 640 by 480 preview.

| Pair and landmark | Rigid (px) | Previous intensity (px) | H&E color (px) | H&E + tip matching (px) |
| --- | ---: | ---: | ---: | ---: |
| 1/2, original margin notch | 20.9 | 16.9 | 13.8 | 13.8 |
| 16/17, original stromal tongue | 10.9 | 5.9 | 10.6 | **5.2** |
| 35/36, original stromal band | 20.9 | 19.5 | 17.5 | 17.5 |
| **Original three, mean** | **17.6** | **14.1** | **14.0** | **12.2** |
| 1/2, curved septum tip | 16.4 | 10.1 | 3.6 | 3.6 |
| **16/17, lower branch junction** | **7.6** | **11.1** | **6.5** | **6.5** |
| **35/36, septum and band junction** | **24.0** | **25.5** | **23.3** | **23.3** |
| 35/36, outer margin notch | 9.2 | 7.8 | 5.2 | 5.2 |
| 23/24, projecting loop apex | 8.9 | 4.9 | 3.3 | 1.4 |
| **Additional five, mean** | **13.2** | **11.9** | **8.4** | **8.0** |

Tip matching reduced the tongue error on 16/17 by 5.4 pixels and the projecting loop error on 23/24 by 1.8 pixels. The other six landmarks, including both junctions, mapped to identical coordinates before and after tip matching. Neither landmark CSV changed. Across all 35 adjacent pairs, mean grayscale correlation on common valid pixels rounded to 0.337 for both H&E exports (9 improved, 17 unchanged within 0.00001, 9 declined). Minimum retained field was 71.2%. The ten distributed overlays still show mismatched tissue margins and cropping. Repeat annotations, an independent series and expert adjudication remain open.

To reproduce the previous result, repeat the download and export command above with `--local-refinement he` and a fresh output path. The bare `--local-refinement` flag also selects intensity. Omitting the flag produces the rigid baseline. Compare exports and score the two landmark files with:

```sh
python scripts/compare_registration.py path/to/he/manifest.json public/data/real/manifest.json
python scripts/landmark_error.py public/data/real/manifest.json docs/pancreas_landmarks.csv
python scripts/landmark_error.py public/data/real/manifest.json docs/pancreas_check_landmarks.csv
```
