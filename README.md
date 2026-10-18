# cv-dataset-auditor

YOLO 目标检测数据集质量检查与标注审查工具。只读扫描，绝不修改你的数据。

## 特性

- **YOLO 标注解析与校验**：class_id 范围、坐标合法性（0-1 归一化）、边界框越界、格式错误、空框。
- **图片健康检查**：缺失、损坏、无法打开的图片。
- **配对检查**：图片缺失标注、孤立标注文件（有标注无图片）。
- **数据泄漏检测**：跨 train/val/test 的字节完全相同图片（MD5）。
- **统计分析**：类别分布、图片尺寸、边界框面积/宽高比分布。
- **可视化**：标注叠加预览图（gallery）。
- **结构化报告**：HTML（可筛选）+ JSON（机器可读）。
- **CI 集成**：`--fail-on error|warning` 控制退出码。

## 安装

Python 3.10+，已在 Python 3.14 上验证。

```bash
pip install -e .
```

依赖：Pillow、PyYAML。

## 快速开始

### 1. 生成带问题的演示数据集

```bash
python examples/generate_dataset.py demo_dataset
```

生成含 7 种故意问题的 YOLO 数据集（train/val/test 三个 split），覆盖：损坏图片、缺标注、孤立标注、非法格式、类别越界、train/val 泄漏、合法空标注。

### 2. 运行审计

```bash
cv-audit demo_dataset -c 3 -o audit-report
```

输出摘要与报告文件：

```
Auditing dataset: .../demo_dataset
Classes: 3
Splits found: test, train, val
...
Reports saved to: .../audit-report
```

### 3. 查看报告

```bash
# HTML 报告（支持按 severity 筛选）
open audit-report/report.html

# JSON 报告
cat audit-report/report.json
```

### 4. 指定类别名

```bash
cv-audit demo_dataset -c 3 --class-names cat dog bird -o audit-report
```

### 5. CI 用法（退出码）

```bash
cv-audit demo_dataset -c 3 --fail-on error   # 有 error 返回 1
cv-audit demo_dataset -c 3 --fail-on warning # 有 error 或 warning 返回 1
cv-audit demo_dataset -c 3 --fail-on never   # 永远返回 0
```

## 命令行参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `dataset_dir` | 数据集目录（必需） | - |
| `-c, --classes` | 类别数（必需） | - |
| `--class-names` | 类别名列表 | None |
| `-o, --output` | 报告输出目录 | `audit-report` |
| `--no-hash` | 跳过 MD5 泄漏检查 | False |
| `--no-visuals` | 跳过标注可视化 | False |
| `--max-visuals` | 每个 split 最多预览数 | 30 |
| `--fail-on` | `error` / `warning` / `never` | `error` |
| `-q, --quiet` | 最小化输出 | False |

## 测试

```bash
python -m unittest discover -s tests -v
```

当前 19 项测试覆盖：合法标注解析、空标注（背景样本）、类别越界、负类别、非法格式、列数不足、坐标越界、框越界、零宽高、混合有效/无效、数据集发现、配对、孤儿标注、损坏图片、缺标注、泄漏检测、端到端演示数据集。

## 架构

```
src/cv_dataset_auditor/
├── scanner.py     # YOLO 数据集布局发现与配对
├── yolo_parser.py # YOLO 标注解析器
├── checker.py     # 审计检查项 + 泄漏检测
├── stats.py       # 统计分析
├── visualizer.py  # 标注叠加可视化
├── reporter.py    # HTML/JSON 报告
└── cli.py         # 命令行入口
```

## 已知限制

- 泄漏检测使用 MD5（字节完全一致），无法识别"近似重复"（缩放/压缩后的泄漏）；近似重复检测作为可选方向，需单独评估误报率后实现。
- 只支持 YOLO 检测格式；segment/pose 格式不在当前范围。
- 不修改任何数据集文件；如需修复请自行处理。

## 开源参考

设计参考了 [yolo-dataset-doctor](https://github.com/Voss0919/yolo-dataset-doctor)（MIT）、[YoloLint](https://github.com/Gabrli/YoloLint)（Apache 2.0）、[yolo-dataset-quality-analysis](https://github.com/picsalex/yolo-dataset-quality-analysis)（MIT）。借鉴细节与自行实现范围见 [docs/references.md](docs/references.md)。

## 许可证

MIT，见 [LICENSE](LICENSE)。
