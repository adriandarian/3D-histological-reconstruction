# Independent connectivity scoring

Run `python -m pipeline.review_score` for the CODA review status. Without submitted independent pathology readings it reports **REVIEW PENDING / NOT EVALUABLE**. A local frozen export and manifest also produce coordinates for the unreviewed candidate connections. To score submissions, generate the manifest using the [review packet](PATHOLOGIST_REVIEW.md), then run from the repository root:

```sh
python -m pipeline.review_score --manifest data/coda-review-manifest.json --reader data/reader-A.geojson data/edges-A.csv --reader data/reader-B.geojson data/edges-B.json > data/independent-report.json
```

Each pair of inputs is independently validated. The report keeps the submitted polygons, edge decisions, confidence and reasons alongside the separate scores and pre-adjudication comparison. Treat qualifications and independence as attestations that the study coordinator must verify. Synthetic inputs are rejected for the CODA CLI. No source images or reviewer identities need to leave the local machine.

## What is frozen

The trace code, point table, derived profile figure and per-slide audit are from commit `2d8437b8f85cdaf52706c8f67b7d7a9c9cb1b4a4`. The local export's profiles.png and audit.csv matched the Git blobs `dee21ecb34990e391cb99721dfbc082476589df4` and `6e95d1f57597d286c92957b288c233764204afe5`, respectively (audit compared as repository text). The local label volume and source transforms were excluded from that commit. This integration pins their current SHA-256 in the scorer and prints both digests in the report. A different generated export must be investigated as a separate artifact before use.

## Reading the report

* The prediction is class 2 of the frozen 160 × 160 × 20 registered viewer volume. The fixed baseline repeats its first plane in this registered frame. Slide 001 seeded both methods. Examine its metrics separately from downstream slides.
* Native outlines are sampled at registered voxel centers using each measured crop's inverse transform, pixel-center convention and scanner level. Dice and IoU quantify the whole target and each target profile with its one-to-one component match on this grid. Smaller-than-grid, overlapping, out-of-field and indeterminate outlines exclude the plane from segmentation and its incident intervals from topology. Competitor polygons are negative tissue for the target mask. Predictions extending into them reduce overlap, and every join lists the competitors its endpoints intersect. An unpredicted competitor does not count as a missed target. Empty unions have undefined overlap. The labels describe lumen geometry at viewer resolution.
* A predicted edge requires face contact between two planar four-connected components. The existing continuity scorer matches components to profiles one-to-one at IoU ≥ 0.10. `supportedLinks`, `falseLinks` and `missedLinks` give TP, FP and FN on exhaustively reviewed intervals. Their sums TP + FP and TP + FN are the predicted and reference link denominators. An unrelated pair with a predicted link contributes FP. `exactSplits` and `exactMerges` additionally require the complete daughter or parent set, respectively. Negative IDs denote unmatched predicted components.
* Every `predictedJoins` entry includes one registered contact pixel, both section checksums and filenames, native level-zero coordinates, candidate component IDs, available reference profile IDs and the verdict. Use the voxel coordinates and the interval's section index in the viewer to find this contact. The range between sections is inferred. The odd-numbered CODA cuts are sampled at a nominal 10 µm interval. The actual cut thickness is unknown. Skipped scheduled samples, missing judgments and ambiguous intervals contribute to exclusion counts.
* Reader agreement uses a separate within-plane one-to-one match at the same IoU threshold so independent names can differ. The report retains each reader's original records, coverage statuses, geometry overlap, unmatched profiles, common links and links unique to either reader. A summary counts exact positive connectivity agreement only for intervals both readers assessed. No adjudicated consensus or clinical accuracy is implied.

The deterministic synthetic regression in [test_review_score.py](../../tests/test_review_score.py) exercises the scoring path, including a known split, false connection, missing daughter, uncertain interval, missing cut and independent disagreement. Run `python -m unittest discover -s tests -p test_review_score.py`.
