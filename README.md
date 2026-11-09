# image-leakage-audit

`audit_leak.py` detects a **code-level, image-level leakage** that is invisible to image-similarity checks:

> A directory-based loader reads every image under a physical training directory, while the train/test membership of each image is maintained by a separate split file. If an evaluation-class directory is placed under the training tree, its evaluation images are read into training and memorised. No duplicate image exists, and the split file itself remains self-consistent.

The audit therefore compares:

- **declared test set**: rows in a split CSV with a test value (default `is_train=0`) and a class in the evaluation-class list;
- **actual readable set**: all image files under the training directory that a directory-based loader can read.

If the intersection is non-empty, the evaluation images can enter training even though no image file is duplicated.

This is the reference implementation for the paper **“目录式加载导致的图像级泄漏与审计”** (Image-Level Leakage Caused by Directory-Based Loading and Its Audit).

## Requirements

- Python **3.8+**
- **No third-party dependencies** (standard library only)
- Works on Linux, macOS and Windows

## Quick start

```bash
git clone https://github.com/chkka1/image-leakage-audit.git
cd image-leakage-audit

python audit_leak.py \
  --train-dir  data/CUB_200_2011/images/base \
  --path-root  data/CUB_200_2011 \
  --split-csv  data/CUB_200_2011/split.csv \
  --eval-classes data/CUB_200_2011/eval_classes.txt
```

The script prints a summary and exits with code **0**, **2** or **3**.

### Example output (leak)

```text
== image-level leakage audit ==
train dir : data/CUB_200_2011/images/base
split CSV : data/CUB_200_2011/split.csv
path root : data/CUB_200_2011
training images readable : 8822
eval classes             : 55
declared eval test rows  : 1627
leaked eval images      : 1046
leaked eval classes     : 35
training-class hold-out : 0

[LEAK] declared evaluation images are readable from the training directory.
  - 001.Black_footed_Albatross
  ...
exit code: 2
```

For CI, use `--json`:

```bash
python audit_leak.py ... --json
```

and check the exit code or the `status` field.

## Input format

### Split CSV

A header is required. By default the script expects:

```csv
path,is_train,class_id
images/base/001.Black_footed_Albatross/Black_Footed_Albatross_0001_796111.jpg,0,001.Black_footed_Albatross
images/novel/002.Laysan_Albatross/Laysan_Albatross_0001_545.jpg,0,002.Laysan_Albatross
images/base/001.Black_footed_Albatross/train_0001.jpg,1,001.Black_footed_Albatross
```

- `path` — image path, absolute or relative. Relative paths are resolved against `--path-root`.
- `is_train` — `1`/`0` or `train`/`test`; values in `--test-values` mean **test/eval**.
- `class_id` — class name. If the CSV has no class column, pass `--class-col ""` and the class is inferred from the image's parent directory.

Column names can be changed:

```bash
--path-col image_path --split-col split --class-col label
```

### Evaluation classes

`--eval-classes` accepts either:

- a file with one class name per line, or
- a comma-separated list: `--eval-classes "001.Black_footed_Albatross,002.Laysan_Albatross"`.

### Training directory

`--train-dir` is the directory a training loader actually reads, for example `images/base` in CUB-200-2011. The script walks it recursively and treats the **first path component** under `--train-dir` as the class directory.

For the CUB example, `--train-dir data/CUB_200_2011/images/base`, `--path-root data/CUB_200_2011`, and CSV paths like `images/base/001.../xxx.jpg` resolve to the same absolute paths.

> The audit only reads file names and paths. It does **not** read image pixels and does not need the image content, so it is cheap enough to run before every training job.

## Exit codes

| Code | Meaning |
|---|---|
| **0** | No declared test image is readable from the training directory. |
| **2** | **Leak**: at least one evaluation-class test image is readable from the training directory. |
| **3** | No eval-class leak, but test images belonging to training classes are readable from the training directory (the training-class hold-out is also contaminated). |
| **1** | Input/IO error (missing file, bad column, etc.). |

Code **2** takes priority over **3** when both are present.

## Options

| Option | Default | Description |
|---|---|---|
| `--train-dir` | required | Training tree the loader reads. |
| `--split-csv` | required | Split CSV with path + split columns. |
| `--eval-classes` | required | File or comma-separated eval class names. |
| `--path-root` | current directory | Root used to resolve relative CSV paths. |
| `--path-col` | `path` | CSV path column. |
| `--split-col` | `is_train` | CSV split column. |
| `--class-col` | `class_id` | CSV class column; `""` infers from the parent directory. |
| `--image-ext` | `.jpg,.jpeg,.png,.bmp,.tif,.tiff,.webp` | Image extensions treated as readable. |
| `--test-values` | `0,false,no,test,val,eval,n` | Values in `--split-col` that mean test/eval. |
| `--json` | off | Print a JSON report only. |

## Reproduce the paper

- `docs/cub-field-audit.md` — how to lay out CUB-200-2011 and run the field audit (35/55 classes, 1,046 leaked images).
- `docs/controlled-experiment.md` — the CIFAR-100 dose-response protocol used in the paper (60/40 class split, 20 support / 20 control / 60 treated, f = 0/25/50/100%, ResNet-18, ConvNeXt-Tiny at f = 0/100%).

The datasets are **not** redistributed here. Download them from their official pages and follow their licences:

- CUB-200-2011: <https://www.vision.caltech.edu/datasets/cub_200_2011/>
- CIFAR-100: <https://www.cs.toronto.edu/~kriz/cifar.html>

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests create a synthetic directory tree only; no real images are needed. They cover exit codes 0, 2 and 3 and the JSON output.

## Licence

MIT — see [`LICENSE`](LICENSE).

## Citation

If this script helps your work, please cite the paper (details will be added after publication):

```text
常开开, 罗小龙, 相龙伟. 目录式加载导致的图像级泄漏与审计[J]. 科技视界, 2026.
```
