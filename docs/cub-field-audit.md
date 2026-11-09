# CUB-200-2011 field audit

This note describes the field audit reported in the paper: 55 evaluation classes, of which 35 are physically under the training tree, and 1,046 evaluation images are read into training.

## Expected dataset layout

The audit assumes the project uses the official CUB directory layout:

```text
CUB_200_2011/
├── images/
│   ├── base/                 # the training loader reads this tree
│   │   ├── 001.Black_footed_Albatross/
│   │   └── ...
│   └── novel/
│       └── ...
├── split.csv
└── eval_classes.txt
```

In the audited project:

- the dataset has 200 classes;
- the project split is **145 Base / 55 Novel** (different from the official 150/50 directory layout);
- `split.csv` has one row per image with `path,is_train,class_id`;
- 35 of the 55 evaluation classes are physically under `images/base/`, and 20 are under `images/novel/`;
- the audit finds **1,046** `is_train=0` images under the training tree, out of **1,627** evaluation images in total;
- the A group (35 classes) has **2,094** images, and the B group (20 classes) has **581** evaluation images.

## Run

```bash
python audit_leak.py \
  --train-dir  CUB_200_2011/images/base \
  --path-root  CUB_200_2011 \
  --split-csv  CUB_200_2011/split.csv \
  --eval-classes CUB_200_2011/eval_classes.txt \
  --json
```

Expected: exit code **2**, `summary.leaked_eval_images == 1046`, `summary.leaked_eval_classes == 35`.

The audit does not modify the dataset and does not need image pixels. It only traverses file names and resolves them against `--path-root`.

## Repair

The paper reports a structural repair: move 35 class directories out of `images/base` and 30 into `images/novel`, so that the two physical trees match the 145/55 class split. The total number of images before and after the move is **11,788**, and the per-image `is_train` labels are unchanged.

After the repair, the same command should return exit code **0** (or **3** only if a training-class hold-out image is still under the training tree).

## Notes

- The dataset itself is not redistributed in this repository. Download CUB-200-2011 from the official Caltech page and follow its licence.
- The repository only contains the audit logic and documentation; it does not include the project's trained checkpoints.
