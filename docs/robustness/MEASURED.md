# Measured H&E source QA and contact sensitivity

The analysis covers every retained section of three locally available H&E cases. All 62 viewer source previews matched the RGB pixels regenerated from their native scans. Among 19 CODA intervals, every proposed contact persisted under the specified perturbations. Small translations changed the contact graph in eight of the nine Roy intervals with an existing contact and in all five TCIA intervals at the larger translation. Stability measures a property of the frozen masks. It cannot identify the tissue or establish continuity through an unsampled cut.

## Measured source checks

For CODA, read each local NDPI at the recorded native origin and pyramid level 3, checking the downsample against the source manifest. For Roy, check the registration manifest digest and regenerate each unwarped Lanczos preview from its native TIFF. For TCIA, rerun the original H&E-only stained-tissue bounding box and normalized preview extraction from each native TIFF. Require the recovered bounding box to match the frozen frame. Count pixels with a mismatch in any RGB channel. The numeric inventories include native and preview file SHA-256, dimensions, mismatch count and green intensity 5th/95th percentiles for each source.

| Series | Pixel QA | Observations on unmarked measured previews |
| --- | --- | --- |
| CODA lung | 20/20 exact native crop reproductions | The large pale space and surrounding stained tissue change outline and orientation across the retained planes. At overview scale some peripheral airspaces are hard to distinguish from the traced lumen. |
| Roy pancreas | 36/36 exact source preview reproductions | Tissue occupies different portions of the frame across sections. Large external white fields and internal bright spaces coexist. A bright cavity alone has uncertain tissue identity. |
| TCIA prostate | 6/6 exact normalized source preview reproductions | Tissue outlines, gaps between tissue pieces and visible seams vary across levels. Normalizing the outer bounding box leaves internal alignment uncertain. |

The visual check used a local unmarked contact sheet containing every section. The analysis did not collect pathology readings. The source pixels and CODA contact sheet stay local. Crops show a subset of a slide at reduced resolution. Pixel equality verifies extraction and linkage, without measuring registration error.

## Perturbation design

Freeze class 2 on each case's registered or organ-normalized viewer grid. Enumerate four-connected components separately on each observed plane. For each adjacent pair, the baseline contains every component pair sharing at least one XY pixel. Keeping component IDs fixed, translate the later labeled plane by 0, 2 or 4 pixels in each positive and negative cardinal direction with zero fill and test minimum contact areas of 1 and 4 pixels. This simulates residual inter-plane displacement at fixed segmentation. Pixels refer to each case's own viewer grid, including approximately 14.13 micrometres per pixel for CODA; uncalibrated Roy and normalized TCIA offsets should not be interpreted as equivalent physical errors. The procedure measures local contact sensitivity, rather than re-estimating the registration.

The table pools lost/gained edges over all four directions for each radius under the one-pixel contact rule. Thus each baseline edge contributes four opportunities at each nonzero radius. The last column applies the four-pixel area rule with zero displacement. Each mask and section pair enters the analysis, including empty pairs. These are deterministic stress directions applied to one specimen per case, not independent replicates or biological false-join rates.

| Series | Baseline positive intervals / all | Baseline edges | 2 px, lost / gained | 4 px, lost / gained | Lost at zero shift, 4-pixel area |
| --- | ---: | ---: | ---: | ---: | ---: |
| CODA | 19 / 19 | 19 | 0 / 0 of 76 baseline opportunities | 0 / 0 of 76 | 0 / 19 |
| Roy | 9 / 35 | 16 | 25 / 1 of 64 | 33 / 1 of 64 | 8 / 16 |
| TCIA | 5 / 5 | 32 | 7 / 0 of 128 | 22 / 4 of 128 | 2 / 32 |

Roy sections 6 to 7 contain two baseline contacts. Both disappear when a minimum of four shared pixels is required, even at zero shift. A viewer should flag the apparent division for inspection. In TCIA, restricting the analysis to whether *any* interval contact survives would hide most changes: at four pixels every interval retained some contact in every direction, yet across directions 22 baseline edges disappeared and four previously absent component pairs touched. The original held-out C/E Dice remain 0.0091 and 0.0000. Repeating perturbations on those known outcomes cannot constitute fresh validation. [TCIA held-out study](../tcia-prostate/README.md)

CODA remained stable under all 18 settings per interval. The tracking method explicitly rewards overlap with the preceding profile, and large projected masks can absorb translations while spanning an incorrect airspace. The publisher outlines the seed plane. The other 19 identities remain **REVIEW PENDING**. Display stable geometric contact separately from independently supported anatomy. [CODA review protocol](../coda-lung/PATHOLOGIST_REVIEW.md)

## Reproduction

From the repository root, install the base requirements and the optional readers:

```sh
python -m pip install -r requirements.txt openslide-python openslide-bin tifffile imagecodecs
python -m scripts.robustness_measured --output data/robustness-measured-repeat
python -m unittest discover -s tests -p test_robustness_measured.py
```

Prepare the sources and frozen exports using the [Roy](../DATA.md), [CODA](../coda-lung/README.md) and [TCIA](../tcia-prostate/README.md) acquisition instructions. Supply the native TCIA TIFFs under `data/tcia/files`. Use `--case roy`, `--case coda` or `--case tcia` to run an available case in isolation. The CLI reports case manifest and label hashes. It only writes numeric CSVs to its output folder.

| Case | Evaluated label file SHA-256 | Per-input and per-interval results |
| --- | --- | --- |
| CODA | `d29253e73d858d62a454ec3ae96ef8b6e2b1512f814c14dacdaf5f5bba4e642e` | [Sources](measured/coda-sources.csv) and [342 interval settings](measured/coda-sensitivity.csv) |
| Roy | `7b33e03a3c303d1e52242994a2ecd01638a96f8daff52bad2d7b577df9dc7ccd` | [Sources](measured/roy-sources.csv) and [630 interval settings](measured/roy-sensitivity.csv) |
| TCIA | `7c40207b476149ad775d098a7a155aaa2ef087bb69460e6b522c130e7aafcd31` | [Sources](measured/tcia-sources.csv) and [90 interval settings](measured/tcia-sensitivity.csv) |
