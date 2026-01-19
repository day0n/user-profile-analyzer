# AI 用户画像分析使用说明

## 功能介绍

基于用户在 AI 创作平台上的工作流使用数据，调用 Gemini AI 分析用户画像，包括：

- **用户类型**：内容创作者、营销人员、个人玩家等
- **活跃度**：高频活跃、中等活跃、轻度使用
- **使用目的**：电商带货、广告营销、社交媒体、个人创作等
- **技能水平**：新手、熟练、专业
- **内容偏好**：短视频、图文、商业广告等

## 环境要求

- Python >= 3.12
- uv 包管理器
- MongoDB 数据库访问权限
- Gemini API Key（配置在 `.env.local` 中的 `GOOGLE_GENAI_API_KEY`）

## 安装依赖

```bash
cd user-profile-analyzer
uv sync
```

## 运行方式

### 基本用法

```bash
# 默认：只分析未处理的用户（ai_profile 为 null）
uv run python -m src.user_profile_analyzer.analyze_profile

# 强制重新分析所有用户（覆盖已有画像）
uv run python -m src.user_profile_analyzer.analyze_profile --force

# 只分析指定用户
uv run python -m src.user_profile_analyzer.analyze_profile --email user@example.com

# 调整并发数（默认 5）
uv run python -m src.user_profile_analyzer.analyze_profile -c 10

# 组合使用：强制重新分析 + 高并发
uv run python -m src.user_profile_analyzer.analyze_profile --force -c 10
```

### 命令行参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--force` | `-f` | 强制重新分析所有用户（覆盖已有画像） | 否 |
| `--email` | `-e` | 只分析指定邮箱的用户 | 无 |
| `--concurrency` | `-c` | 并发数 | 5 |

### 服务器运行（生产环境）

```bash
# SSH 到服务器
ssh ubuntu@ec2-54-205-248-143.compute-1.amazonaws.com

# 进入项目目录
cd /path/to/user-profile-analyzer

# 拉取最新代码
git pull

# 同步依赖
uv sync

# 运行分析（使用 .env.local 配置）
uv run python -m src.user_profile_analyzer.analyze_profile

# 强制重新分析所有用户
uv run python -m src.user_profile_analyzer.analyze_profile --force

# 后台运行（推荐，防止 SSH 断开中断）
nohup uv run python -m src.user_profile_analyzer.analyze_profile --force > analyze.log 2>&1 &

# 查看运行日志
tail -f analyze.log
```

## 进度显示

运行时会显示实时进度和 Token 统计：

```
分析进度:  50%|█████     | 800/1579 [05:30<05:20] input_tokens=12,456,000, output_tokens=3,200,000, cost=$2.5234
```

## 数据说明

### 输入数据

从 `user_workflow_profile` 集合读取用户的 Top 10 工作流数据：
- 工作流名称、签名、运行次数
- 节点类型组合
- 用户输入的图片（`data.imageBase64` 字段，实际存储 URL）
- 用户输入的文本（`data.inputText` 字段）

### 输出数据

分析结果保存到 `user_workflow_profile.ai_profile` 字段：

```json
{
  "primary_purpose": "广告营销",
  "user_type": "营销人员",
  "activity_level": "轻度使用",
  "content_focus": ["商业广告", "TVC"],
  "skill_level": "新手",
  "tags": ["广告", "营销", "视频制作"],
  "summary": "尝试使用AI创作平台制作商业广告TVC的营销人员。",
  "workflow_analysis": [
    {
      "rank": 1,
      "purpose": "广告营销",
      "confidence": "高",
      "reason": "工作流名称包含"商业广告TVC"..."
    }
  ],
  "analyzed_at": "2026-01-19T10:51:58",
  "model": "gemini-2.0-flash"
}
```

## 成本估算

使用 Gemini 2.0 Flash 模型：

| 项目 | 价格 |
|------|------|
| 输入 | $0.10 / 1M tokens |
| 输出 | $0.40 / 1M tokens |
| 图片 | ~258-1000 tokens/张 |

### Token 计算规则

- **文本**：约 4 字符 = 1 token
- **图片**：≤384×384 像素 = 258 tokens，更大图片按 768×768 分块
- **视频**：约 258 tokens/秒

### 预估成本

| 用户数 | 预计输入 tokens | 预计输出 tokens | 预计成本 |
|--------|----------------|----------------|----------|
| 15 | 12K | 6K | $0.004 |
| 1,500 | 25M | 5M | $4.5 |

## 注意事项

1. **默认行为**：只分析 `ai_profile` 为 null 的用户，不会重复分析
2. **强制模式**：使用 `--force` 会覆盖所有已有画像，重新分析
3. **并发控制**：默认并发数为 5，避免 API 限流，可适当提高到 10-20
4. **网络要求**：需要能访问 Gemini API 和 CloudFront 图片资源
5. **图片限制**：每个用户最多分析 15 张图片，每个工作流最多 5 张

## 相关文件

| 文件 | 说明 |
|------|------|
| `src/user_profile_analyzer/analyze_profile.py` | AI 画像分析主脚本 |
| `src/user_profile_analyzer/generate_profile.py` | 用户画像数据生成脚本 |
| `src/user_profile_analyzer/web_ui.py` | Web UI 数据展示 |

## 常见问题

### Q: 如何只重新分析部分用户？

```bash
# 方法1：指定邮箱
uv run python -m src.user_profile_analyzer.analyze_profile --email user@example.com

# 方法2：手动清空指定用户的 ai_profile 后重新运行
```

### Q: 运行中断了怎么办？

直接重新运行即可，已分析的用户会被跳过（除非使用 `--force`）。

### Q: 如何查看分析结果？

```bash
# 启动 Web UI
uv run python -m src.user_profile_analyzer.web_ui
# 访问 http://localhost:7860
```
