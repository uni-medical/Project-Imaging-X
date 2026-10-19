# Query Normalization

Use these rules when mapping user language to `search_datasets.py` arguments.

## Modality

- `MRI`, `MR` -> `--modality mr`
- `X-ray`, `radiograph` -> `--modality x-ray`
- `ultrasound`, `US` -> `--modality ultrasound`
- `pathology`, `histopathology`, `WSI` -> `--modality pathology`

If the user names a rare modality that is not covered above, pass it through as a raw modality filter.
If the local index has no coverage for that modality, say the index is sparse for that modality, avoid irrelevant near matches from other modalities, and still run the **mandatory** supplementary web search from the parent `SKILL.md` §4 (mark web-only hits as `web supplement`).

## Task

- `segmentation`, `mask`, `contour` -> `--task seg`
- `classification`, `screening` -> `--task cls`
- `detection`, `localization`, `bbox` -> `--task det`
- `registration` -> `--task reg`
- `reconstruction` -> `--task rec`
- `prediction` -> `--task pred`

## Dimension

- `3D`, `volumetric` -> `--dim 3d`
- `2D`, `slice-based` -> `--dim 2d`
- `video`, `sequence` -> `--dim video`

## Preference Mapping

- `open`, `public`, `direct download`, `公开可下载` -> `--access open --prefer-open`
- `registration required is acceptable` -> do not set `--access`; keep `--prefer-open`
- `with labels`, `annotated` -> `--label true`
- `without labels` -> `--label false`
- Platform-specific asks:
  - `Kaggle` -> `--platform kaggle.com`
  - `TCIA` -> `--platform cancerimagingarchive.net`
  - `Grand Challenge` -> `--platform grand-challenge.org`
  - `OpenNeuro` -> `--platform openneuro.org`

## Disease and Anatomy

Pass anatomy and disease as raw normalized strings:

- `brain MRI glioma segmentation` -> `--structure brain --disease glioma`
- `kidney tumor CT` -> `--structure kidney --disease tumor`

If the user names subtype terms like `GBM` or `LGG`, use them as disease filters first.
