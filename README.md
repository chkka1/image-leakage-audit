# image-leakage-audit

`audit_leak.py` 用于检测一种**代码层面、图像级**、且图像相似性检查无法发现的泄漏：

> 目录式加载器会读取物理训练目录下的全部图像，而每张图像的训练/测试归属由另一套划分文件维护。如果某个评测类的目录被放在训练目录树下，其评测图就会被读入训练并被模型记住。此时没有重复图像，划分文件本身也保持自洽。

因此，审计比较两个集合：

- **声明测试集**：划分 CSV 中测试值（默认 `is_train=0`）且类别属于评测类列表的样本；
- **实际读取集**：训练目录下目录式加载器能够读取的全部图像文件。

两者交集非空，即说明评测图进入了训练集，即使没有任何图像文件重复。

本仓库是论文《目录式加载导致的图像级泄漏及其审计》的参考实现。

## 环境要求

- Python **3.8+**
- **无第三方依赖**（仅使用标准库）
- 支持 Linux、macOS 和 Windows

## 快速开始

```bash
git clone https://github.com/chkka1/image-leakage-audit.git
cd image-leakage-audit

python audit_leak.py \
  --train-dir  data/CUB_200_2011/images/base \
  --path-root  data/CUB_200_2011 \
  --split-csv  data/CUB_200_2011/split.csv \
  --eval-classes data/CUB_200_2011/eval_classes.txt
```

脚本会打印检查摘要，并以 **0**、**2** 或 **3** 退出。

### 示例输出（存在泄漏）

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

在 CI 中可使用 `--json`：

```bash
python audit_leak.py ... --json
```

然后检查退出码或输出中的 `status` 字段。

## 输入格式

### 划分 CSV

必须有表头。默认要求以下列：

```csv
path,is_train,class_id
images/base/001.Black_footed_Albatross/Black_Footed_Albatross_0001_796111.jpg,0,001.Black_footed_Albatross
images/novel/002.Laysan_Albatross/Laysan_Albatross_0001_545.jpg,0,002.Laysan_Albatross
images/base/001.Black_footed_Albatross/train_0001.jpg,1,001.Black_footed_Albatross
```

- `path`：图像路径，绝对路径或相对路径。相对路径按 `--path-root` 解析。
- `is_train`：`1`/`0` 或 `train`/`test`；取值属于 `--test-values` 时表示**测试/评测**。
- `class_id`：类别名。如果 CSV 没有类别列，可传 `--class-col ""`，此时类别从图像所在父目录推断。

列名可以修改：

```bash
--path-col image_path --split-col split --class-col label
```

### 评测类列表

`--eval-classes` 支持两种形式：

- 文件：每行一个类名；
- 逗号分隔的列表：`--eval-classes "001.Black_footed_Albatross,002.Laysan_Albatross"`。

### 训练目录

`--train-dir` 是训练加载器实际读取的目录，例如 CUB-200-2011 中的 `images/base`。脚本会递归遍历该目录，并把 `--train-dir` 下的**第一级路径分量**视为类目录。

以 CUB 为例，`--train-dir data/CUB_200_2011/images/base`、`--path-root data/CUB_200_2011`，以及 CSV 中形如 `images/base/001.../xxx.jpg` 的路径会解析到同一绝对路径。

> 本检查只读取文件名和路径，**不读取图像像素**，也不需要图像内容，因此开销很低，可以在每次训练前运行。

## 退出码

| 退出码 | 含义 |
|---|---|
| **0** | 训练目录下没有可读的声明测试图像。 |
| **2** | **存在泄漏**：至少有一张评测类测试图可从训练目录读取。 |
| **3** | 没有评测类泄漏，但训练类测试图可从训练目录读取（训练类留出集也被污染）。 |
| **1** | 输入/IO 错误（文件缺失、列名错误等）。 |

当同时出现 2 和 3 时，退出码 **2** 优先。

## 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--train-dir` | 必填 | 加载器读取的训练目录树。 |
| `--split-csv` | 必填 | 包含路径列和划分列的 CSV。 |
| `--eval-classes` | 必填 | 评测类文件，或逗号分隔的类名。 |
| `--path-root` | 当前目录 | 解析 CSV 中相对路径的根目录。 |
| `--path-col` | `path` | CSV 路径列名。 |
| `--split-col` | `is_train` | CSV 划分列名。 |
| `--class-col` | `class_id` | CSV 类别列名；设为 `""` 时从父目录推断。 |
| `--image-ext` | `.jpg,.jpeg,.png,.bmp,.tif,.tiff,.webp` | 视为可读图像的扩展名。 |
| `--test-values` | `0,false,no,test,val,eval,n` | `--split-col` 中表示测试/评测的取值。 |
| `--json` | 关闭 | 只输出 JSON 报告。 |

## 复现论文

- `docs/cub-field-audit.md`：如何组织 CUB-200-2011 并运行现场审计（35/55 类、1046 张泄漏图）。
- `docs/controlled-experiment.md`：论文使用的 CIFAR-100 剂量-反应实验协议（60/40 类划分，20 张支撑集 / 20 张对照 / 60 张处理，f = 0/25/50/100%，ResNet-18，ConvNeXt-Tiny 取 f = 0/100%）。

数据集**不随仓库分发**。请从官方页面下载，并遵守各自许可：

- CUB-200-2011：<https://www.vision.caltech.edu/datasets/cub_200_2011/>
- CIFAR-100：<https://www.cs.toronto.edu/~kriz/cifar.html>

## 测试

```bash
python -m unittest discover -s tests -v
```

测试只创建合成目录树，不需要真实图像；覆盖退出码 0、2、3 以及 JSON 输出。

## 许可证

MIT，详见 [`LICENSE`](LICENSE)。

## 引用

如果本脚本对你的工作有帮助，请引用论文（发表后补充卷期页码）：

```text
常开开, 罗小龙, 相龙伟. 目录式加载导致的图像级泄漏及其审计[J]. 科技视界, 2026.
```
