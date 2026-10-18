# 项目讲解稿：cv-dataset-auditor

## 1. 解决什么问题

YOLO 目标检测训练前，数据集里常见几类"看不见"的致命问题：
- 一张图同时出现在 train 和 val（**泄漏**）→ 验证指标虚高，部署后大跌；
- 图片损坏或缺失，训练器静默跳过 → 数据量与预期不符；
- 标注 class_id 越界、坐标越界、格式错 → 训练崩溃或学到坏样本；
- 有标注没图（孤儿标注）、有图没标注（缺标注）→ 配对混乱；
- 类别分布严重不均、图片尺寸混杂 → 影响训练稳定性。

这些问题用眼睛根本查不过来。本工具以**只读审计**方式扫描数据集，输出分级 findings（error/warning）、统计分析、标注叠加预览和可筛选报告。

## 2. 关键设计

### 只读哲学
绝不修改数据、绝不创建缺失标注、绝不做"自动修复"。用户需要修复时自行处理——审计工具的职责是**发现问题并给出证据**，不是替用户改数据。

### 空标注 = 背景样本
空 `.txt` 是合法的背景图（无对象），不报错；这符合主流 YOLO 生态。与"缺标注文件"严格区分：缺文件是 warning，空文件是合法。

### 泄漏检测用 MD5，刻意不用近似哈希
MD5 只报告**字节完全一致**的图片，零误报。近似重复（缩放/压缩后泄漏）不做自动检测——"看起来像"的判定会引入不可控误报，作为已知限制写入文档，而不是假装能检测。

### 配对按 stem
图片与标注按文件名 stem 配对（`a.jpg` ↔ `a.txt`），与后缀无关，天然支持跨格式布局。

### 退出码即 CI 语义
`--fail-on error|warning|never` 控制退出码，让审计可直接塞进训练流水线做质量门禁。

### 布局发现兼容两种结构
- Ultralytics 风格：`images/train` + `labels/train`
- Split-first：`train/images` + `train/labels`

## 3. 实际贡献

| 内容 | 说明 |
|------|------|
| 演示数据集生成器 | 7 种故意问题，图片用伪随机 seed 保证唯一（防"模板同源"意外泄漏） |
| 检查项分类体系 | pairing/image/label/leakage 四类，每类明确 severity |
| 统计 + 可视化 | 类别分布、图片尺寸、bbox 面积/宽高比、标注叠加 gallery |
| 报告 | HTML 内嵌 JS 筛选 + JSON 机器可读 |
| 测试 | 19 项，含端到端演示数据集审计（断言每类问题都被抓到） |

## 4. 踩过的坑（真实记录）

1. **演示数据集"意外泄漏"**：最初所有图片用同一模板生成，JPEG 字节完全相同 → MD5 泄漏检测报出 6 处"泄漏"，实际只有 1 处刻意注入。改用伪随机 seed 逐图生成后，泄漏检测精确报 1 处。这反过来证明 MD5 泄漏检测是敏锐的。
2. **孤儿标注测试失败**：最初删掉图片留标注，导致该 split 无图像文件，布局发现找不到 split。改为"保留图片 + 额外孤立标注"。
3. **非法格式测试断言错位**：`not numbers` 有 2 个 token，报"expected 5 values"而非"non-numeric"——断言与实现语义要对齐。
4. **bash 管道吞退出码**：本地验证 `cmd | tail` 让 `$?` 变成 tail 的退出码；CI 脚本用 `set +e` + 独立 `$?` 捕获，语义正确。

## 5. 如何演示

```bash
# 1) 生成带 7 种问题的数据集
python examples/generate_dataset.py demo_dataset

# 2) 审计（有 error → 退出码 1）
cv-audit demo_dataset -c 3 --class-names cat dog bird -o audit-report --fail-on error
echo $?   # 1

# 3) 查看报告
open audit-report/report.html    # 可筛选 errors/warnings
cat audit-report/report.json

# 4) 预览标注叠加
ls audit-report/gallery/train/   # _annotated.jpg

# 5) 质量门禁用法
cv-audit demo_dataset -c 3 --fail-on warning   # 训练前强制检查
```

演示要点：泄漏 1 处被抓、损坏图被抓、缺标注/孤儿标注/越界/非法格式逐类命中；退出码语义可脚本化。
