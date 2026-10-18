# 开源参考与借鉴

## 1. yolo-dataset-doctor (Voss0919)

- **仓库**: https://github.com/Voss0919/yolo-dataset-doctor
- **许可证**: MIT
- **参考版本**: 主分支，v1.x
- **借鉴设计**:
  - "只读检查、不修改标注"的核心哲学
  - 结构化检查项分类：Pairing、Labels、Format、Leakage、Duplication、Images、Statistics
  - 有意义的退出码用于 CI 集成
  - 可筛选的 HTML 报告设计
  - stem-based 图像/标注配对策略
  - 将空 .txt 标注视为合法背景样本的思路
- **本项目自行实现**:
  - 完全独立的代码实现，未复制其源码
  - 不同的报告格式和检查项组织方式
  - 增加近似重复检测（感知哈希）作为独立可选功能
  - 增加类别分布统计图表和边界框分布可视化
  - GitHub API 集成（自动创建 Issue 报告）

## 2. YoloLint (Gabrli)

- **仓库**: https://github.com/Gabrli/YoloLint
- **许可证**: Apache 2.0
- **参考版本**: 2025年7月版
- **借鉴设计**:
  - 分模块验证：结构验证、标注验证、尺寸验证的三层检查
  - CLI 子命令组织方式
- **本项目自行实现**:
  - 合并为统一的扫描流程而非三个独立 CLI
  - 增加泄漏检测和统计功能
  - 不包含自动修复功能（本工具只读）
  - 不同的报告格式

## 3. FiftyOne / yolo-dataset-quality-analysis (picsalex)

- **仓库**: https://github.com/picsalex/yolo-dataset-quality-analysis
- **许可证**: MIT
- **参考版本**: 主分支
- **借鉴设计**:
  - 标注元数据统计（面积、宽高比等）的计算维度
  - 利用 FiftyOne 做交互式可视化的思路
- **本项目自行实现**:
  - 不依赖 FiftyOne（减少依赖复杂度）
  - 使用纯 Python + Pillow 生成静态可视化
  - 独立实现所有统计计算