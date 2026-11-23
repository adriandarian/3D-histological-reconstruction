# Import an independent reading

CODA bronchiole identity after the seed slide is **REVIEW PENDING**. The existing AI observations are ineligible as pathology references. Follow the [blinding protocol](PATHOLOGIST_REVIEW.md) before readers see the prediction. Keep all submissions, identity keys, crops and outputs under ignored local `data/`.

## Prepare the source frame

Install the [trace dependencies and generate the local export](README.md#reproduce-and-inspect), then run from the repository root:

```sh
python -m pipeline.review_import coda-manifest data/coda-review-manifest.json
python -m pipeline.review_import annotations data/coda-review-manifest.json data/A.geojson data/A-edges.csv data/A-import.json
python -m pipeline.review_import landmarks data/coda-review-manifest.json data/A-landmarks.json data/A-tre.json
```

Each command requires a fresh output file. Archive raw submissions and their digests before comparing predictions or adjudicating. Qualifications and blinding are attestations that the study coordinator must verify.

The manifest command checks each NDPI against its acquisition SHA-256 and scanner MPP tags. It records filenames, digests, dimensions, sampling, crop origin, scale, size and the affine from native pixel-edge coordinates into the first slide's native frame. The calculation converts between pixel edges and OpenCV pixel centers at both ends. Section numbers increase by two. The sampling interval is nominally 10 µm and cut thickness is unknown. The importer pins canonical JSON digests for the local candidate trace and source manifest during integration. Importing either annotations or landmarks rejects a changed CODA manifest. For another case, use the manifest structure in the [synthetic test fixture](../../tests/test_review_import.py). Set `mpp` to null when calibration is unavailable.

## Reader files

A reader's GeoJSON object uses type `FeatureCollection` with the following members.

| Member | Contents |
| --- | --- |
| `case`, `coordinates` | Case ID (`coda-lung` for CODA) and literal `native_level0_pixel_edges`. Origin is upper left; X increases rightward and Y downward. |
| `reviewer` | Object with blinded `id`, text `qualifications`, ISO `date`, `blinded: true`, and `kind: "PATHOLOGIST"`. Use `"SYNTHETIC"` for software tests. |
| `planes` | Array of objects with `slide`, `sha256`, `status`, `reason`. `REVIEWED` attests exhaustive delineation of target profiles in the frozen review field. Outline competitors separately. An empty reviewed plane records no observed target. Use `INDETERMINATE` for partial or obscured evidence. An omitted plane is unreviewed. |
| `intervals` | Array of objects with `source_slide`, `target_slide`, `status`, `reason`. `REVIEWED` means both endpoint planes are reviewed and all target connections have been assessed. Explicit uncertain edges are allowed. Use interval-wide `INDETERMINATE` for incomplete assessment or a missing sampled slide. Omitted intervals are unreviewed. |
| `features` | One `Feature` per profile. Properties include globally unique `id` within the submission, native `slide` filename, `sha256`, `role` (`TARGET` or `COMPETITOR`), `status` (`OBSERVED` or `INDETERMINATE`), numeric `confidence` in [0,1] and free-text `reason`. Geometry is a nondegenerate simple GeoJSON `Polygon` with one explicitly closed exterior ring. Holes and multipart polygons are unsupported. |

Draw on the native scan or map packet pixel edges into level zero before import: multiply each coordinate by the scale in `frames.csv`, then add its slide-specific crop origin. Reading packets and predicted masks have different scales.

The edge file is CSV with header `source,target,type,reason,confidence`, or a JSON array of objects with those fields. Endpoints refer to earlier and later profile IDs. Positive relationships connect two target profiles. Each split has one `SPLITS` row per daughter. Each merge has one `MERGES` row per parent. One-to-one links use `CONTINUES`. `UNRELATED` records an explicit negative and `INDETERMINATE` an unresolved correspondence. Mark unresolved many-to-many events as indeterminate. Record each endpoint pair once. Profile IDs can differ between readers.

For registration, submit a JSON object with `case`, `coordinates`, and `reviewer` as above, `withheld_from_registration: true`, and a `landmarks` array. Each landmark needs `id`, `source_slide`, `target_slide`, `source_sha256`, `target_sha256`, `source_xy`, and `target_xy`. Coordinates are level-zero pixel-edge pairs for the same visible landmark on successive retained slides. The source is projected through the common frame and back through the inverse target transform. The report gives individual errors and the arithmetic mean in target pixels, plus physical errors for the calibrated subset. An empty observation set yields **NOT EVALUABLE**. Registration fitting points and AI profile locations are ineligible.

Use the [independent scoring commands](INDEPENDENT_SCORING.md) after freezing all submissions.
