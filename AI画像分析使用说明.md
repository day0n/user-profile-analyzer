# AI 用户画像分析

基于用户工作流数据 + Gemini 3 Flash 多模态分析，识别潜在商业客户。

## 快速开始

```bash
# 安装依赖
uv sync

# 分析所有未处理用户
uv run python -m src.user_profile_analyzer.analyze_profile

# 强制重新分析所有用户
uv run python -m src.user_profile_analyzer.analyze_profile --force

# 分析指定用户
uv run python -m src.user_profile_analyzer.analyze_profile --email user@example.com

# 调整并发数（默认 5）
uv run python -m src.user_profile_analyzer.analyze_profile -c 20

# 组合使用
uv run python -m src.user_profile_analyzer.analyze_profile --force -c 20
```

## 命令行参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--force` | `-f` | 强制重新分析所有用户 | 否 |
| `--email` | `-e` | 只分析指定用户 | 无 |
| `--concurrency` | `-c` | 并发数 | 5 |

## 服务器运行

```bash
# 后台运行（推荐）
nohup uv run python -m src.user_profile_analyzer.analyze_profile --force -c 20 > analyze.log 2>&1 &

# 查看日志
tail -f analyze.log
```

## 输出数据结构

分析结果保存到 `user_workflow_profile.ai_profile`：

```json
{
  "primary_purpose": "电商带货",
  "user_type": "电商卖家",
  "activity_level": "轻度使用",
  "content_focus": ["商品展示视频", "产品图片"],
  "tags": ["电商", "服装", "带货"],
  "summary": "尝试制作服装商品视频的电商新手。",

  "positioning": {
    "industry": "服装",
    "business_scale": "个人卖家",
    "platform": "抖音",
    "content_type": "商品展示视频"
  },

  "business_potential": {
    "score": 8,
    "stage": "尝试期",
    "barrier": "不熟悉工作流搭建",
    "recommendation": "推荐服装行业模板"
  },

  "workflow_analysis": [...],
  "analyzed_at": "2026-01-19T12:00:00",
  "model": "gemini-3-flash-preview"
}
```

## 查询潜在客户

```javascript
// 高潜力 + 尝试期（最值得运营）
db.user_workflow_profile.find({
  "ai_profile.business_potential.score": { $gte: 7 },
  "ai_profile.business_potential.stage": "尝试期"
})

// 按行业筛选
db.user_workflow_profile.find({
  "ai_profile.positioning.industry": "服装"
})

// 按平台筛选
db.user_workflow_profile.find({
  "ai_profile.positioning.platform": "抖音"
})
```

## 成本估算

**模型**：Gemini 3 Flash Preview

| 项目 | 价格 |
|------|------|
| 输入 | $0.50 / 1M tokens |
| 输出 | $3.00 / 1M tokens |

**预估**：~1,500 用户约 $25-30

## 注意事项

1. 默认只分析 `ai_profile` 为 null 的用户
2. 使用 `--force` 会覆盖已有画像
3. 运行中断后直接重新运行，已分析的用户会跳过
