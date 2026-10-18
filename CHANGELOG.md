# CHANGELOG

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/).

## [0.1.0] - 2026-10-18

### Added

- 项目初始公开版本。
- YOLO 标注解析与校验：class_id 范围、归一化坐标合法性、边界框越界、列数、数值格式、零宽高。
- 空标注文件视为合法背景样本（无对象图片）。
- 数据集布局发现：Ultralytics 风格（images/train + labels/train）与 split-first（train/images + train/labels）。
- 配对检查：图片缺标注、孤立标注文件。
- 图片健康检查：损坏、无法打开的图片。
- MD5 泄漏检测：跨 train/val/test 的字节完全相同图片。
- 统计分析：类别分布、图片尺寸、边界框面积与宽高比。
- 标注叠加可视化 gallery。
- HTML（可筛选）+ JSON 双格式报告。
- CLI：`cv-audit`，支持 `--fail-on error|warning|never` 退出码控制、`--no-hash`、`--no-visuals`。
- 19 项自动化测试（含端到端演示数据集审计）。
- 演示数据集生成脚本 `examples/generate_dataset.py`（7 种故意问题）。
- GitHub Actions CI（Python 3.10/3.12/3.14，单测 + CLI 端到端 + 退出码验证）。
- MIT 许可证。

### Known Limitations

- 泄漏检测仅覆盖字节完全相同的图片（MD5）；近似重复（缩放/压缩后泄漏）不检测，避免误报。
- 仅支持 YOLO detection 格式。
- 只读审计，不修复任何问题。