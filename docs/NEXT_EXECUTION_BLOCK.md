# Next execution block: Integration + evidence-first H&E validation

**Status:** Execution work package, not completed code. Prepared November 23, 2026.
**Git branch:** integration/histology-evidence-to-main (derived from research/tcia-tumor-extent).
**Target:** main, via a reviewed DRAFT pull request, without auto-merge.
**North star:** [GOAL.md](../GOAL.md) on main.

## Mission

Bring the research results from PRs #6–#8 together with the production viewer and its evidence standards. Make scientific status truthful and machine-verifiable. Then build the annotation-import and scoring machinery needed for independent H&E continuity validation. Do not mistake a green build, 3D mesh, high Dice or merged branch for verified tissue anatomy.

At preparation time, Vercel production was READY on main commit 76f407963d2f679d48012625dec9fb74ba0b6394. The research branch was 21 commits ahead and three behind main. Much of that diff reflects historical stacked PRs: PR #5 already reached main through PR #4. **Do not duplicate or overwrite these features.**

## Part A: Reconcile and validate integration (do this first)

1. Fetch main and the research branches. Checkout integration/histology-evidence-to-main.
2. Inspect merge ancestry with git log and git merge-base, then merge origin/main into the integration branch. Preserve GOAL.md and its README link; resolve conflicts without deleting research features, source provenance, or negative results.
3. Inventory all dataset cases and check that the viewer still supports the branching synthetic duct, H01 cortical capillary, FAFB neuronal bifurcation, H01 vascular fork, pancreas H&E and TCIA prostate negative result.
4. Keep CODA H&E local-only until actual NDPI redistribution terms are verified. Never publish raw CODA whole slides or source crops merely because they can be downloaded. Identify other image and segmentation licenses (FAFB, H01, TCIA) and preserve attribution.
5. Separate displayed evidence states: SYNTHETIC, REAL EM / INDEPENDENT REFERENCE, EXPLORATORY H&E, LOCAL-ONLY H&E / REVIEW PENDING, FAILED HELD-OUT H&E. The browser must never imply all meshes are scientifically validated.
6. Confirm source selection/coordinates work: clicking a reconstructed region should show the corresponding **measured** native-section pixels, registration status and overlays. CODA must fail gracefully when local-only assets are absent; do not show fake bundled data.
7. Build and run tests on the user's computer. Document commands and results. Suggested order:

    git fetch origin
    git switch integration/histology-evidence-to-main
    git merge origin/main
    python -m pip install -r requirements.txt
    python -m unittest discover -s tests
    npm ci
    npx playwright install chromium
    npm run test:e2e
    npm run build
    npm run preview

Check setup instructions before using local generated datasets. Test the built viewer in Chromium, with screenshots and network-console review. A passing Vercel build does not replace interactive checks.

**Gate A:** The integration PR is reviewable, not merged; no data-license violations; GOAL.md is preserved; tests and build results are reported honestly; case selection, source links and evidence labels work. Do not trigger or promote a production deployment.

## Part B: Build independent H&E annotation scoring tools

The next scientific question is whether a **named structure on a measured H&E slide** truly continues or branches across consecutive sampled sections. Start with the [CODA bronchiole candidate](coda-lung/README.md) and the [pathologist review packet](coda-lung/PATHOLOGIST_REVIEW.md). The candidate is frozen at commit 2d8437b (verify full commit and artifact checksums). The 20 retained slides are 001, 003, ..., 039 at nominal 10 µm sampling, not a continuous collection of every physical cut. Only the first has a published reference outline in this window.

Implement code that can run **without inventing pathologist input**:

- A documented schema for each reviewer: identity or blinded ID, qualifications, source slide and checksum, native level-zero GeoJSON polygons, unique profile ID, parent/daughter identifiers, status, confidence, reason, and edge type (CONTINUES, SPLITS, MERGES, UNRELATED, INDETERMINATE).
- Strict validation of coordinates, polygons, slide order, missing cuts, crop-to-native transforms, identifiers, and inconsistent edges; unit tests must cover wrong and missing metadata.
- A CLI to import real independent reader GeoJSON plus edge-table CSV/JSON; source datasets stay in ignored local folders where licensing requires.
- An explicit graph scorer based on frozen predictions and **independent reference annotations**: TP, FP, FN inter-section connections and branch events, missed or false joins, per-plane IoU/Dice if masks exist, excluded/ambiguous intervals and denominators; compare with a simple fixed/nearest-mask baseline.
- A reader agreement report before adjudication, with any disagreements retained. Absent review data should display NOT EVALUABLE / REVIEW PENDING, not 100% accuracy or synthetic expert results.
- Independent registration landmark importer and target registration error report. Only use physical units if scanner X/Y calibration is verified; report sampled Z interval separately from actual cut thickness.
- Source-linked evidence output for any predicted join: the two measured sections on either side, original coordinates, mask and reference status.
- **Synthetic fixtures** for regression tests: true split, false join, missed edge, unrelated profiles, indeterminate gap, missing cut, malformed annotations and identity collision. Synthetic labels are never presented as human-review results.
- Preserve the frozen prediction. Any new segmentation algorithms are separate versioned experiments, not silent replacements.

**Gate B:** An independent reader can supply annotations and get reproducible scoring, but without expert annotations the CODA candidate remains explicitly UNVERIFIED. Neither an AI visual reader nor matching 19 points supplies qualified independent pathology ground truth.

## Part C: Preserve TCIA negative result and prevent metric laundering

PR #8's sparse-anchor tumor interpolation fails on held-out TCIA sections: predicted Dice C = 0.0091 and E = 0.0000; nearest-anchor C = 0.0434, E = 0.0625. Keep the frozen score file and prediction digest. Add a check to ensure the report and viewer label this as **negative / failed generalization**, not validated tumor mapping.

Document plausible explanations (large biological change, sample gaps, orientation/registration, organ normalization, multifocal lesions) as hypotheses. A new version must use a *new* independent evaluation split, not tune on held-out C/E then call that a fresh result.

## Data and evidence matrix to include in PR

| Case | Primary use | Known limits |
| --- | --- | --- |
| Synthetic Y duct | Known 3D topology and software regression | Already aligned, engineered contrast |
| Roy pancreas | Optical H&E visualization and registration QA | Unknown physical Z and anatomical identity |
| H01 capillary | Dense serial EM with published corrected labels | 21 extra graph links, near-stationary-baseline Dice |
| FAFB neuron | Independent human traced 1-to-2 topology in EM | Not H&E; no independent full membrane contours |
| H01 vascular fork | Ambiguous vascular transition and abstention | Exact fork unresolved |
| CODA lung | Candidate real serial H&E bronchiole trace | Independent downstream expert labels pending; local images |
| TCIA prostate | Negative held-out H&E extent reconstruction | Sparse, uncalibrated organ frame; poor Dice |

## Definition of done

- Git integration branch incorporates the current main and retains GOAL.md.
- All relevant available Python tests, Chromium tests, and frontend production builds were actually run and outcomes logged. Built UI inspected and any failing cases documented.
- Properly permitted research cases are usable and accurately labeled; local-only cases and negative results remain clear.
- Independent H&E reference schema, importer, graph scoring and synthetic unit tests exist; actual CODA pathology reference is pending until supplied by qualified independent reviewers.
- README and project guide reflect shipped vs local-only vs experimental work.
- One **draft integration PR** records the technical changes, outputs and limits. Do not merge or deploy automatically.
- Never fabricate measurements, expert readings, release rights, or successful scientific validation.

## References

- [Project goal](../GOAL.md)
- [Research direction](RESEARCH_DIRECTION.md)
- [Project guide](PROJECT_GUIDE.md)
- [CODA acquisition](CODA_LUNG.md)
- [CODA trace](coda-lung/README.md)
- [Review protocol](coda-lung/PATHOLOGIST_REVIEW.md)
- [TCIA negative result](tcia-prostate/README.md)
- [H01 capillary](H01_CAPILLARY.md)
- [FAFB bifurcation](REAL_BIFURCATION.md)
