# Controlled CIFAR-100 experiment

This note records the dose-response protocol used in the paper. The repository's `audit_leak.py` is the audit tool; the training code is deliberately not included because the paper's claim is about the audit object, not about a new model.

## Data split

- Dataset: CIFAR-100 (100 classes, 500 training and 100 test images per class).
- Class split: 60 training classes / 40 evaluation classes, drawn once and fixed.
- For each evaluation class, its 100 test images are permuted once by class index and split into three disjoint subsets:
  - **support**: 20 images, used only to build the nearest-class-mean prototypes; never written into the training directory;
  - **control**: 20 images, never written into the training directory (never-leaked baseline);
  - **treated**: 60 images, a fraction `f` of which is copied into the training directory.

## Dose levels

`f` is the fraction of each evaluation class's treated images that is readable by the training loader:

| f | images per class | images over 40 eval classes |
|---|---|---|
| 0% | 0 | 0 |
| 25% | 15 | 600 |
| 50% | 30 | 1,200 |
| 100% | 60 | 2,400 |

The dose is set **per image**, not per class, so that a class can be partially contaminated. This avoids the ceiling effect that occurs when a whole class is read in at once.

## Training

- Backbone: ImageNet-pretrained ResNet-18; input 64×64.
- Optimiser: AdamW; cosine learning-rate schedule; 20 epochs; batch size 256; 3 random seeds.
- At the end of training the classifier head is discarded; the frozen features are used with a nearest-class-mean classifier.
- Replication: ConvNeXt-Tiny, only at `f=0` and `f=100%`.

## Metrics

- `acc_all`: accuracy over all 100 test images of an evaluation class (the number that would be reported in a paper).
- `acc_control`: accuracy on the 20 control images that were never readable by the loader.
- `acc_leaked`: accuracy on the `f × 60` treated images that were actually copied into the training directory.
- `Δwithin = acc_leaked − acc_control`, computed within the same model and the same class.

The primary quantity is `Δwithin`; `acc_all` is reported to show what a reader would see in the paper.

## Expected qualitative results

- `acc_all` increases with `f`; `acc_control` stays stable at roughly 77–79%.
- `Δwithin` is about 21–22 percentage points for ResNet-18 and about 10 percentage points for ConvNeXt-Tiny.
- `Δwithin` does not keep increasing with `f` because `acc_leaked` saturates near 100%; the aggregate `acc_all` still increases because the contaminated fraction of the evaluation set grows.
- A small positive spillover on control images is possible; it makes the reported `Δwithin` conservative.

These are the values reported in the paper (ResNet-18: 22.58 / 20.96 / 21.18 percentage points; ConvNeXt-Tiny: 10.08 percentage points; 95% CI [19.03, 23.33] and [8.29, 11.88] respectively).

## Reproducing

1. Download CIFAR-100 from the official page; do not commit the images to this repository.
2. Build the 60/40 class split and the support/control/treated partition with a fixed seed.
3. For each `f`, copy the corresponding treated files into a separate training directory.
4. Train the backbone on the resulting directory, then evaluate with the frozen-feature nearest-class-mean classifier.
5. Run `audit_leak.py` on the same directory and split CSV; at `f>0` it should return **2** and report the expected number of leaked images, connecting the experiment back to the audit.

The dataset and trained checkpoints are not redistributed here.
