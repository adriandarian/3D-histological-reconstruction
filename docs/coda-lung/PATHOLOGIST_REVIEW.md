# Independent review of CODA bronchiole region 3

**Status: awaiting pathologist annotations.** The publisher supplies a seed outline on slide 001. The checked public annotation set contains no outline on 007 or 009. The points used in PR 6 were placed by an AI reader. The branch status and agreement with pathologists are unscored. [Publisher annotation directory](https://drive.google.com/drive/folders/1JeFbOY3kVRQ0s3JwaJvKZ6_UKEfsRxNv)

## Prepare a reading set

After [generating the CODA trace](README.md), run the following command from the repository root with a new destination directory.

~~~sh
python -m scripts.coda_reader_packet data/coda-independent-review
~~~

Give each pathologist a separate copy of the reading set and the reading instructions below. The packet contains 20 unmarked source crops, one explicitly marked seed key on 001, and a mapping to the original NDPI files. Crops use native slide orientation and approximately 0.883 µm per pixel. Their fields were located using registration. Provide access to the original NDPI scans for higher magnification and off-crop tissue. Keep measured images local under the acquisition terms. Withhold the PR 6 predictions, AI marks, audit and suspected transition from the readers until their calls are frozen.

## Reading instructions

Starting from the outlined structure on the seed key, trace the epithelial-lined airspace on each retained slide. Return lumen polygons for each profile as GeoJSON Polygons in native level-zero slide pixels, with the slide filename and a unique profile ID on each feature. The origin is top left, X increases rightward and Y downward. For coordinates drawn on a crop, multiply pixel-edge coordinates by two and add the origin in frames.csv.

For each adjacent pair, record the earlier and later slide and profile IDs, relationship (continues, splits, merges, unrelated or indeterminate), reason and confidence. Record both daughter IDs for a split. Mark obscured or off-field regions explicitly. Describe the epithelial or wall evidence supporting the identification and any plausible competing profile. Record reader identifier, pathology qualifications, review date and prior exposure to predictions. Each reader submits independently before adjudication.

## Compare the frozen readings

Use the candidate from commit 2d8437b. Report reader agreement before any consensus review. Compare the predicted mask to each native outline separately, then report supported, missed and extra links with their denominators. List indeterminate and unreviewed intervals separately. For 007 to 009, inspect the flanking slides 005 and 011 and distinguish a spatially resolved pair of daughters from an expanded single airspace or segmentation spill. A change in projected area cannot establish a bifurcation. The odd-numbered slides skip a physical cut. Even agreement on a split localizes the transition only to the supported interval.

See the [native-coordinate import schema and landmark QA commands](ANNOTATION_IMPORT.md) for submission formats and checks.
