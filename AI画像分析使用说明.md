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

# 后台运行（推荐，防止 SSH 断开中断）
nohup uv run python -m src.user_profile_analyzer.analyze_profile > analyze.log 2>&1 &

# 查看运行日志
tail -f analyze.log
```

### 可选参数

```bash
# 调整并发数（默认 5，可提高到 10-20 加快速度）
uv run python -m src.user_profile_analyzer.analyze_profile -c 10

# 只分析指定用户
uv run python -m src.user_profile_analyzer.analyze_profile --email user@example.com
```

## 数据说明

### 输入数据

从 `user_workflow_profile` 集合读取用户的 Top 10 工作流数据：
- 工作流名称、签名、运行次数
- 节点类型组合
- 用户输入的图片/视频/文本

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
- 输入价格：$0.10 / 1M tokens
- 输出价格：$0.40 / 1M tokens

| 用户数 | 预计输入 tokens | 预计输出 tokens | 预计成本 |
|--------|----------------|----------------|----------|
| 15 | 12K | 6K | $0.004 |
| 1,500 | 1.2M | 600K | $0.4 |

## 注意事项

1. **首次运行**：会分析所有 `ai_profile` 为 null 的用户
2. **重复运行**：只会分析新增的未分析用户
3. **重新分析**：如需重新分析某用户，需先将其 `ai_profile` 设为 null
4. **并发控制**：默认并发数为 5，避免 API 限流
5. **网络要求**：需要能访问 Gemini API 和 S3 图片资源

## 相关文件

- `src/user_profile_analyzer/analyze_profile.py` - AI 画像分析主脚本
- `src/user_profile_analyzer/generate_profile.py` - 用户画像数据生成脚本
- `src/user_profile_analyzer/web_ui.py` - Web UI 数据展示
