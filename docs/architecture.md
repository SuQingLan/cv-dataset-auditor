# 架构说明

## 处理流程

```
数据集目录
   │
   ▼
┌───────────────┐  布局发现（Ultralytics / split-first 两种布局）
│  scanner.py   │──► DatasetLayout {splits: {train/val/test: SplitLayout}}
└───────────────┘
   │  按 stem 匹配图片/标注
   ▼
┌───────────────┐  每 split 审计：
│  checker.py   │  ├─ 图片健康（损坏/无法打开）
│               │  ├─ 配对（缺标注/孤立标注）
│               │  ├─ 标注（解析 + 校验）
│               │  └─ 统计收集
└───────────────┘
   │  MD5 跨 split 哈希比对
   ▼
┌───────────────┐  泄漏检测（字节完全相同）
│ check_leakage │──► findings
└───────────────┘
   │
   ▼
┌───────────────┐  类别分布、图片尺寸、bbox 面积/宽高比
│  stats.py     │
└───────────────┘
   │
   ▼
┌───────────────┐  标注叠加预览图（gallery）
│ visualizer.py │
└───────────────┘
   │
   ▼
┌───────────────┐  HTML（可筛选）+ JSON 报告；--fail-on 控制退出码
│  reporter.py  │
└───────────────┘
```

## 设计决策

1. **只读哲学**：审计绝不修改数据集文件、绝不创建缺失标注。用户需要修复时自行处理。
2. **空标注即背景**：空 .txt 是合法的背景样本，不报告为错误；这与主流 YOLO 生态一致。
3. **stem 配对**：图片与标注按文件名 stem 配对，支持 `.jpg`/`.txt` 不同后缀。
4. **泄漏检测用 MD5**：只报告字节完全一致的图片，零误报；近似重复（缩放/压缩后）不做自动检测，避免为"看起来像"引入不可控误报，作为文档中的已知限制。
5. **退出码语义**：`--fail-on error`（默认）有 error 返回 1；`--fail-on warning` error/warning 都返回 1；`--fail-on never` 恒返回 0。便于 CI 分级控制。
6. **报告可筛选**：HTML 报告内嵌 JS 按 severity 过滤，无需重跑审计。

## 模块依赖

```
scanner ← checker ← reporter ← cli
   │         │
   └──► stats.py    └──► visualizer.py
```

依赖仅向下的方向，无环。

## 检查项清单

| 类别 | 检查项 | severity |
|------|--------|----------|
| pairing | 图片缺标注 | warning |
| pairing | 孤立标注（无对应图片） | warning |
| image | 损坏/无法打开 | error |
| label | 类别越界 | error |
| label | 坐标非法 | error |
| label | 框越界 | error |
| label | 格式/列数错误 | error |
| leakage | 跨 split 完全重复 | error |