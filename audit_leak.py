#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_leak.py — detect image-level leakage caused by directory-based loading.

The audit compares two sets:

1. the images declared as evaluation/test images by a split CSV;
2. the images that a directory-based loader can actually read from a
   training directory (all image files under that directory).

If the two sets intersect for an evaluation class, the evaluation images can
enter training without any duplicate file being visible.  The script is
deliberately dependency-free (Python standard library only).

Exit codes
----------
0  no leakage found
2  evaluation images declared as test are readable from the training directory
3  no eval-image leak, but test images of training classes are in the training
   directory (the training-class hold-out is also contaminated)
1  input/IO error

Example
-------
python audit_leak.py \
  --train-dir data/CUB_200_2011/images/base \
  --path-root data/CUB_200_2011 \
  --split-csv data/CUB_200_2011/split.csv \
  --eval-classes data/CUB_200_2011/eval_classes.txt

The CSV must contain a path column and a split/is_train column; a class column
is optional (the parent directory name is used when it is absent).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

__version__ = "1.0.0"

# Keep output stable when the script is called from a non-UTF-8 console (e.g. Windows GBK).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")
DEFAULT_TEST_VALUES = ("0", "false", "no", "test", "val", "eval", "n")


def norm_path(path: Union[os.PathLike, str]) -> str:
    """Return a case-normalised absolute path string for set comparison."""
    return os.path.normcase(os.path.normpath(str(Path(path).resolve())))


def parse_exts(raw: str) -> Set[str]:
    exts: Set[str] = set()
    for item in raw.split(","):
        ext = item.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = "." + ext
        exts.add(ext)
    return exts or set(DEFAULT_IMAGE_EXTS)


def parse_eval_classes(raw: str) -> Set[str]:
    """Accept a file (one class per line) or a comma/space-separated list."""
    p = Path(raw)
    if p.is_file():
        values: List[str] = []
        with p.open("r", encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip().strip('"').strip("'")
                if line and not line.startswith("#"):
                    values.append(line)
    else:
        cleaned = raw.replace(";", ",").replace("\t", ",")
        values = [v.strip().strip('"').strip("'") for v in cleaned.split(",")]
    values = [v for v in values if v]
    if not values:
        raise ValueError("--eval-classes is empty")
    return set(values)


def class_from_path(path_value: str) -> str:
    """Infer a class name from the parent directory of a CSV image path."""
    return Path(path_value).parent.name


def read_declared_rows(
    csv_path: Path,
    path_col: str,
    split_col: str,
    class_col: Optional[str],
    test_values: Set[str],
) -> Iterable[Dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("the split CSV has no header")
        fields = {f.strip(): f for f in reader.fieldnames}
        if path_col not in fields:
            raise ValueError(
                "path column %r not found; columns: %s" % (path_col, ", ".join(fields))
            )
        if split_col not in fields:
            raise ValueError(
                "split column %r not found; columns: %s" % (split_col, ", ".join(fields))
            )
        if class_col is not None and class_col not in fields:
            raise ValueError(
                "class column %r not found; columns: %s" % (class_col, ", ".join(fields))
            )
        for row in reader:
            raw_path = (row.get(fields[path_col]) or "").strip().strip('"').strip("'")
            if not raw_path:
                continue
            split = (row.get(fields[split_col]) or "").strip().strip('"').lower()
            if class_col is not None:
                cls = (row.get(fields[class_col]) or "").strip().strip('"').strip("'")
            else:
                cls = class_from_path(raw_path)
            yield {
                "path": raw_path,
                "split": split,
                "class": cls,
            }


def collect_train_images(train_dir: Path, exts: Set[str]) -> Tuple[Dict[str, str], Dict[str, int]]:
    """Return {normalised absolute path: class} and per-class counts."""
    actual: Dict[str, str] = {}
    class_counts: Dict[str, int] = {}
    for p in train_dir.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in exts:
            continue
        try:
            rel = p.relative_to(train_dir)
        except ValueError:
            continue
        cls = rel.parts[0] if len(rel.parts) > 1 else ""
        actual[norm_path(p)] = cls
        class_counts[cls] = class_counts.get(cls, 0) + 1
    return actual, class_counts


def audit(
    train_dir: Path,
    split_csv: Path,
    eval_classes: Set[str],
    path_root: Path,
    path_col: str,
    split_col: str,
    class_col: Optional[str],
    exts: Set[str],
    test_values: Set[str],
) -> Dict[str, object]:
    if not train_dir.is_dir():
        raise ValueError("--train-dir is not a directory: %s" % train_dir)
    if not split_csv.is_file():
        raise ValueError("--split-csv is not a file: %s" % split_csv)
    if not path_root.is_dir():
        raise ValueError("--path-root is not a directory: %s" % path_root)

    actual, class_counts = collect_train_images(train_dir, exts)

    declared_eval: Dict[str, Dict[str, str]] = {}
    declared_trainclass: Dict[str, Dict[str, str]] = {}
    eval_rows = 0
    all_test_rows = 0
    for row in read_declared_rows(split_csv, path_col, split_col, class_col, test_values):
        if row["split"] not in test_values:
            continue
        all_test_rows += 1
        resolved = path_root / row["path"]
        key = norm_path(resolved)
        row = dict(row, resolved=str(resolved))
        if row["class"] in eval_classes:
            eval_rows += 1
            declared_eval[key] = row
        else:
            declared_trainclass[key] = row

    leaked = {k: v for k, v in declared_eval.items() if k in actual}
    trainclass_hit = {k: v for k, v in declared_trainclass.items() if k in actual}

    leaked_classes = sorted({v["class"] for v in leaked.values()})
    leaked_examples = [
        {
            "class": v["class"],
            "declared_path": v["path"],
            "resolved_path": v["resolved"],
        }
        for _, v in sorted(leaked.items())[:20]
    ]
    trainclass_classes = sorted({v["class"] for v in trainclass_hit.values()})
    trainclass_examples = [
        {
            "class": v["class"],
            "declared_path": v["path"],
            "resolved_path": v["resolved"],
        }
        for _, v in sorted(trainclass_hit.items())[:20]
    ]

    if leaked:
        status, exit_code = "leak", 2
    elif trainclass_hit:
        status, exit_code = "training_class_holdout", 3
    else:
        status, exit_code = "ok", 0

    return {
        "status": status,
        "exit_code": exit_code,
        "train_dir": str(train_dir),
        "split_csv": str(split_csv),
        "path_root": str(path_root),
        "summary": {
            "training_images_readable": len(actual),
            "training_classes_readable": len(class_counts),
            "eval_classes": len(eval_classes),
            "declared_test_rows_all": all_test_rows,
            "declared_test_rows_eval_classes": eval_rows,
            "leaked_eval_images": len(leaked),
            "leaked_eval_classes": len(leaked_classes),
            "training_class_holdout_images": len(trainclass_hit),
        },
        "leaked_classes": leaked_classes,
        "leaked_examples": leaked_examples,
        "training_class_holdout_classes": trainclass_classes,
        "training_class_holdout_examples": trainclass_examples,
    }


def print_human(result: Dict[str, object]) -> None:
    status = result["status"]
    summary = result["summary"]  # type: ignore[index]
    print("== image-level leakage audit ==")
    print("train dir : %s" % result["train_dir"])
    print("split CSV : %s" % result["split_csv"])
    print("path root : %s" % result["path_root"])
    print("training images readable : %s" % summary["training_images_readable"])
    print("eval classes             : %s" % summary["eval_classes"])
    print("declared eval test rows  : %s" % summary["declared_test_rows_eval_classes"])
    print("leaked eval images      : %s" % summary["leaked_eval_images"])
    print("leaked eval classes     : %s" % summary["leaked_eval_classes"])
    print("training-class hold-out : %s" % summary["training_class_holdout_images"])

    if status == "leak":
        print("\n[LEAK] declared evaluation images are readable from the training directory.")
        for cls in result["leaked_classes"][:20]:  # type: ignore[index]
            print("  - %s" % cls)
        for item in result["leaked_examples"][:5]:  # type: ignore[index]
            print("    %s" % item["declared_path"])
        print("\nexit code: 2")
    elif status == "training_class_holdout":
        print("\n[HOLDOUT] test images of training classes are readable from the training directory.")
        for cls in result["training_class_holdout_classes"][:20]:  # type: ignore[index]
            print("  - %s" % cls)
        print("\nexit code: 3")
    else:
        print("\n[OK] no declared test image is readable from the training directory.")
        print("\nexit code: 0")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Audit directory-based image-level leakage by comparing the declared split "
                    "with the images a loader can actually read from the training tree.",
    )
    p.add_argument("--train-dir", required=True, type=Path,
                   help="root directory the training loader reads (e.g. images/base)")
    p.add_argument("--split-csv", required=True, type=Path,
                   help="CSV with a path column and a split/is_train column")
    p.add_argument("--eval-classes", required=True,
                   help="file (one class per line) or comma-separated list of eval class names")
    p.add_argument("--path-root", type=Path, default=Path.cwd(),
                   help="root used to resolve paths in the CSV (default: current directory)")
    p.add_argument("--path-col", default="path",
                   help="CSV column containing image paths (default: path)")
    p.add_argument("--split-col", default="is_train",
                   help="CSV column containing train/test membership (default: is_train)")
    p.add_argument("--class-col", default="class_id",
                   help="CSV column containing class names (default: class_id; "
                        "use '' to infer from parent directory)")
    p.add_argument("--image-ext", default=",".join(DEFAULT_IMAGE_EXTS),
                   help="comma-separated image extensions (default: common formats)")
    p.add_argument("--test-values", default=",".join(DEFAULT_TEST_VALUES),
                   help="comma-separated values in --split-col that mean test/eval")
    p.add_argument("--json", action="store_true", help="print a JSON report only")
    p.add_argument("--version", action="version", version="%(prog)s " + __version__)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        eval_classes = parse_eval_classes(args.eval_classes)
        exts = parse_exts(args.image_ext)
        test_values = {v.strip().lower() for v in args.test_values.split(",") if v.strip()}
        class_col = args.class_col.strip() or None
        result = audit(
            train_dir=args.train_dir,
            split_csv=args.split_csv,
            eval_classes=eval_classes,
            path_root=args.path_root,
            path_col=args.path_col,
            split_col=args.split_col,
            class_col=class_col,
            exts=exts,
            test_values=test_values,
        )
    except (OSError, ValueError, csv.Error) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_human(result)
    return int(result["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
