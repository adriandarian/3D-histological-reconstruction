# 3D Histological Reconstruction

Research and proof-of-concept workspace for reconstructing **3D tissue volumes from ordered, digitized serial histology sections** and exploring them alongside conventional 2D whole-slide imagery.

> **Status:** Planning and research only. This repository currently contains a technical POC plan; no processing pipeline or viewer has been implemented or validated. Not for clinical/diagnostic use.

## Start here

**[Read the full proof-of-concept plan](docs/POC_PLAN.md)** for background, datasets, verified research references, architecture, suggested implementation steps, CLI and data-layout conventions, validation criteria, risks, and a phased roadmap.

### Proposed first demonstration

1. Obtain an openly licensed, **ordered** series of 30–50 tissue sections. Verify section order, spacing, and physical pixel scale rather than assuming them.
2. Inspect, register, and export the sections as a correctly spaced 3D volume; include registration QA, an unregistered baseline, and provenance.
3. Display a cross-linked 2D view (OpenSeadragon) and rotatable 3D view (Three.js or an existing volume viewer) with a Z-slice slider and synchronized XY location.
4. Measure whether reconstruction improves continuity and landmark alignment, rather than judging only by visual smoothness.
5. Graduate to tiled whole-slide images and chunked OME-Zarr only after the small-data pipeline works.

### Starter dataset

[Serial Section Histopathology Image Dataset (Mendeley Data, CC BY 4.0)](https://data.mendeley.com/datasets/fzskwpzs5j/1): 48 colon and 36 pancreas serial images **at each of two magnifications**, 10× and 40×, as 1280×960 RGB TIFFs. Do not interpret the two magnifications as twice the number of physical cuts. Verify ordering and section spacing from source metadata / authors before claiming real-world Z measurements.

### Scientific foundations

- [CODA, Nature Methods (2022)](https://www.nature.com/articles/s41592-022-01650-9) — large-tissue, cellular-resolution reconstruction from serial histology.
- [VALIS](https://valis.readthedocs.io/en/stable/) — rigid and nonrigid serial pathology slide registration.
- [RAPID, Scientific Reports (2026)](https://www.nature.com/articles/s41598-026-46776-4) — robust large-WSI registration, including sparsely sampled slides.
- [Lila Sciences MOSAIC (2026)](https://www.lila.ai/news/seeing-molecules-from-any-direction) — inspiration for a **future** cross-modal research track, **not** a method for 3D histological reconstruction.

## Principles

- Preserve **measured** versus **interpolated/inferred** data distinctly.
- Record physical units, missing sections, deformation transforms, and confidence/QA scores.
- Start CPU-first with public research data. Never commit patient data or proprietary slides.
- Separate the scientific pipeline from the web viewer; make outputs inspectable in independent tools.

See [docs/POC_PLAN.md](docs/POC_PLAN.md) for details.
