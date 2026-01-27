"""
AI 用户画像分析脚本

功能：
1. 获取用户 Top 10 完整工作流数据（包含图片/视频）
2. 调用 Gemini 3 Flash 多模态分析工作流目的
3. 生成用户画像并保存到 user_workflow_profile.ai_profile

运行方式：
    cd user-profile-analyzer

    # 本地环境
    uv run python -m src.user_profile_analyzer.analyze_profile

    # 正式环境
    APP_ENV=prod uv run python -m src.user_profile_analyzer.analyze_profile

    # 自定义并发数
    APP_ENV=prod uv run python -m src.user_profile_analyzer.analyze_profile -c 10

    # 只处理指定用户
    APP_ENV=prod uv run python -m src.user_profile_analyzer.analyze_profile --email user@example.com
"""

import asyncio
import os
import json
import argparse
import re
import httpx
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi
from tqdm import tqdm
from google import genai
from google.genai import types


def load_env():
    """加载环境变量"""
    app_env = os.environ.get("APP_ENV")
    if app_env:
        env_file = f".env.{app_env}"
    else:
        env_file = ".env.local"

    env_path = Path(__file__).resolve().parent.parent.parent / env_file
    load_dotenv(env_path)

    return env_file


# Prompt 模板
ANALYSIS_PROMPT = """你是一个用户行为分析专家，专注于理解用户的真实使用意图和商业价值。请分析以下用户在AI创作平台上运行的工作流，判断每个工作流的目的，并对用户进行精准分类。

## 用户基本信息
- 统计周期：2024年10月1日 - 2025年1月27日
- 总运行次数：{total_runs}
- 活跃天数：{active_days}

## 用户 Top {workflow_count} 工作流
以下是用户运行最多的工作流，请仔细分析每个工作流的节点组合、输入内容、图片素材，理解用户的真实使用意图。

{workflows_text}

## 节点类型说明
- imageInput: 图片输入（用户上传的素材）
- textInput: 文本输入（用户的 prompt/描述）
- imageToImage: 图生图（风格转换、修图等）
- imageMaker: 文生图
- videoMaker: 图生视频
- textToVideo: 文生视频
- textGenerator: AI 文本生成
- scriptSplit: 脚本/文案分割
- imageUpscaler: 图片放大/增强
- textToSpeech: 文字转语音
- videoLipSync: 视频口型同步
- musicGenerator: AI 音乐生成

## 7大用户分类体系

**重要：必须从以下7个大类中选择1个，并选择对应的子分类！**

### 1. 电商上架转化
**核心本质：** 只用于电商平台商品上架的静态图片素材
- **输出形态：** 图片（非视频）
- **使用场景：** 商品主图、详情页、SKU对比图、白底图、Listing优化
- **判断思路：** 用户在为电商平台准备商品展示图片，目的是上架和展示
- **子分类（按商品品类）：**
  - 服装/鞋包
  - 美妆/护肤
  - 家居/家具
  - 3C数码
  - 食品/饮料
  - 母婴/玩具
  - 珠宝/配饰
  - 其他品类

### 2. 电商营销/投放
**核心本质：** 具有营销属性的电商视频内容，用于在TK、IG等社交平台投放
- **输出形态：** 视频为主
- **使用场景：** TikTok广告、Instagram推广、抖音带货、短视频营销
- **判断思路：** 用户在制作用于投放和带货的视频广告，有明确的营销转化目的
- **子分类（按商品品类）：**
  - 服装/鞋包
  - 美妆/护肤
  - 家居/家具
  - 3C数码
  - 食品/饮料
  - 母婴/玩具
  - 珠宝/配饰
  - 其他品类

### 3. 品牌广告及商业广告
**核心本质：** TVC、品牌认知塑造，目的是提升品牌形象而非直接销售
- **输出形态：** 高质量视频或图片
- **使用场景：** 品牌TVC、企业宣传片、品牌形象片、商业广告
- **判断思路：** 用户在为品牌做形象宣传，强调品牌认知而非直接卖货
- **子分类（按行业）：**
  - 快消品牌
  - 科技/互联网
  - 汽车/出行
  - 金融/保险
  - 教育/培训
  - 房产/地产
  - 餐饮/食品
  - 其他行业

### 4. 社媒内容与IP
**核心本质：** 真人KOL内容、明确体现社媒属性的内容创作
- **输出形态：** 视频为主，真人出镜
- **使用场景：** KOL内容、博主视频、社交媒体原创内容、IP打造
- **判断思路：** 用户在制作真人出镜的社媒内容，有明确的博主/KOL属性
- **子分类（按内容领域）：**
  - 美妆/穿搭博主
  - 美食博主
  - 生活方式博主
  - 科技/数码博主
  - 娱乐/搞笑博主
  - 知识/教育博主
  - 其他博主

### 5. 影视创作
**核心本质：** 强调叙事性、镜头语言的影视内容创作
- **输出形态：** 视频
- **使用场景：** 短剧、微电影、MV、动画、叙事性内容
- **判断思路：** 用户在创作有叙事性和镜头语言的影视内容，强调故事和艺术表达
- **子分类（按内容类型）：**
  - 漫剧/动画
  - 短剧/微电影
  - MV/音乐视频
  - 纪录片
  - 其他影视

### 6. 设计
**核心本质：** 海报、Logo等平面设计和视觉设计
- **输出形态：** 图片
- **使用场景：** 海报设计、Logo设计、品牌视觉、UI设计、插画
- **判断思路：** 用户在进行平面设计或视觉设计工作
- **子分类（按设计类型）：**
  - 海报设计
  - Logo/品牌视觉
  - UI/界面设计
  - 插画/艺术
  - 其他设计

### 7. 其他
**核心本质：** 无法归入以上6类的内容
- **子分类：** 无

## 分类优先级（当用户同时符合多个特征时）
电商上架转化 > 电商营销/投放 > 品牌广告及商业广告 > 社媒内容与IP > 影视创作 > 设计 > 其他

## 分析要求

1. **分析每个工作流的目的**：
   - 理解用户的真实意图（不要机械匹配关键词）
   - 从输出形态（图/视频）、内容特征、使用场景综合判断
   - 判断属于7大类中的哪一类，以及对应的子分类

2. **精准用户定位**：
   - 用户所属行业（从图片内容、文案关键词推断）
   - 用户的业务规模（从使用频率、内容复杂度推断）
   - 用户主要发布的平台（从内容格式、风格推断）

3. **评估商业价值潜力**：
   - 评估用户当前阶段（尝试期、成长期、成熟期、流失期）
   - 分析可能阻碍用户继续使用的因素
   - 给出针对性的运营建议

## 输出格式（JSON）
{{
  "workflow_analysis": [
    {{
      "rank": 1,
      "category": "工作流所属大类（7大类之一）",
      "subcategory": "工作流所属子分类",
      "purpose": "工作流目的描述",
      "confidence": "高/中/低",
      "reason": "判断理由（简短）"
    }}
  ],
  "user_category": "【必须从7大类中选择1个】电商上架转化 | 电商营销/投放 | 品牌广告及商业广告 | 社媒内容与IP | 影视创作 | 设计 | 其他",
  "user_subcategory": "用户所属子分类（根据大类选择对应的子分类）",
  "user_profile": {{
    "primary_purpose": "用户主要使用目的",
    "user_type": "用户类型标签",
    "activity_level": "高频活跃/中等活跃/轻度使用",
    "content_focus": ["内容偏好1", "内容偏好2"],
    "tags": ["标签1", "标签2", "标签3"],
    "summary": "一句话总结用户画像（30字内）"
  }},
  "positioning": {{
    "industry": "具体行业",
    "business_scale": "业务规模（个人/小型团队/中型企业/大型品牌/无法判断）",
    "platform": "主要平台",
    "content_type": "内容类型"
  }},
  "business_potential": {{
    "score": 8,
    "stage": "尝试期/成长期/成熟期/流失期",
    "barrier": "可能的阻碍因素",
    "recommendation": "运营建议"
  }}
}}

## 商业潜力评分标准（score 1-10）
- 9-10分：明确的商业需求，高频使用，有持续付费潜力
- 7-8分：有商业倾向，处于尝试或成长期
- 5-6分：可能有商业需求但不明确
- 3-4分：偏向个人使用，商业价值较低
- 1-2分：纯粹个人娱乐或测试

## 重要提示
- 如果信息不足无法判断子分类，填写"无法判断"
- 不要猜测，基于实际内容判断
- 子分类必须从对应大类的选项中选择

只输出JSON，不要其他内容。"""


class AIProfileAnalyzer:
    """AI 用户画像分析器"""

    def __init__(self, concurrency: int = 5):
        """
        初始化分析器

        Args:
            concurrency: 并发数，默认5（Gemini API 限流考虑）
        """
        # MongoDB 配置
        mongo_uri = os.getenv("MONGO_ATLAS_URI")
        mongo_db = os.getenv("MONGO_DB")

        if not mongo_uri or not mongo_db:
            raise ValueError("请确保环境变量中配置了 MONGO_ATLAS_URI 和 MONGO_DB")

        self.mongo_client = AsyncIOMotorClient(
            mongo_uri,
            server_api=ServerApi('1')
        )
        self.db = self.mongo_client[mongo_db]

        # 集合引用
        self.flow_task_collection = self.db["flow_task"]
        self.profile_collection = self.db["user_workflow_profile"]

        # Gemini 配置
        gemini_api_key = os.getenv("GOOGLE_GENAI_API_KEY")
        if not gemini_api_key:
            raise ValueError("请确保环境变量中配置了 GOOGLE_GENAI_API_KEY")

        self.client = genai.Client(api_key=gemini_api_key)
        self.model_name = 'gemini-2.0-flash'

        # 配置 - 时间范围从2024年10月1日到2025年1月27日
        self.start_date = datetime(2024, 10, 1)
        self.end_date = datetime(2025, 1, 27, 23, 59, 59)
        self.top_n = 10  # Top 10 工作流
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)

        # 统计
        self.success_count = 0
        self.skip_count = 0
        self.error_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def get_users_to_analyze(self, specific_email: Optional[str] = None, force: bool = False) -> List[Dict]:
        """获取需要分析的用户列表

        Args:
            specific_email: 只分析指定邮箱的用户
            force: 强制重新分析所有用户（包括已有画像的）
        """
        if specific_email:
            # 只处理指定用户
            cursor = self.profile_collection.find(
                {"user_email": specific_email},
                {"user_id": 1, "user_email": 1, "stats": 1, "top_workflows": 1}
            )
        elif force:
            # 强制模式：获取所有用户
            cursor = self.profile_collection.find(
                {},
                {"user_id": 1, "user_email": 1, "stats": 1, "top_workflows": 1}
            )
        else:
            # 默认模式：只获取 ai_profile 为 null 的用户
            cursor = self.profile_collection.find(
                {"ai_profile": None},
                {"user_id": 1, "user_email": 1, "stats": 1, "top_workflows": 1}
            )

        return await cursor.to_list(length=None)

    async def get_workflow_full_data(self, user_id: str, signature: str) -> Optional[Dict]:
        """
        获取工作流的完整数据（包含节点输入）

        通过签名匹配找到对应的 flow_task
        """
        # 查找该用户在指定时间范围内的任务，找到签名匹配的
        cursor = self.flow_task_collection.find(
            {
                "user_id": user_id,
                "created_at": {"$gte": self.start_date, "$lte": self.end_date},
                "status": "success"
            },
            {
                "nodes": 1,
                "created_at": 1
            }
        ).sort("created_at", -1).limit(100)

        async for task in cursor:
            nodes = task.get("nodes", [])
            task_signature = self._generate_signature(nodes)
            if task_signature == signature:
                return {
                    "nodes": nodes,
                    "created_at": task.get("created_at")
                }

        return None

    def _generate_signature(self, nodes: List[Dict]) -> str:
        """生成工作流签名"""
        if not nodes:
            return "empty"

        from collections import defaultdict
        type_counts = defaultdict(int)
        for node in nodes:
            node_type = node.get("type", "unknown")
            type_counts[node_type] += 1

        signature = ",".join(
            f"{k}:{v}" for k, v in sorted(type_counts.items())
        )
        return signature

    def _extract_media_urls(self, nodes: List[Dict]) -> Dict[str, List[str]]:
        """从节点中提取图片和视频 URL"""
        images = []
        videos = []
        texts = []

        for node in nodes:
            node_type = node.get("type", "")
            data = node.get("data", {})
            inputs = node.get("inputs", {})

            # 合并 data 和 inputs
            all_data = {**data, **inputs}

            # 提取图片 - 检查 imageBase64 字段（实际存的是 URL）
            img_url = all_data.get("imageBase64", "")
            if img_url and isinstance(img_url, str) and img_url.startswith("http"):
                images.append(img_url)

            # 提取视频 URL
            video_url = all_data.get("videoUrl", "") or all_data.get("video_url", "") or all_data.get("videoBase64", "")
            if video_url and isinstance(video_url, str) and video_url.startswith("http"):
                videos.append(video_url)

            # 提取文本输入
            input_text = all_data.get("inputText", "") or all_data.get("text", "") or all_data.get("prompt", "")
            if input_text and isinstance(input_text, str) and len(input_text) > 5:
                texts.append(input_text)

            # 遍历其他字段查找可能的媒体 URL
            for key, value in all_data.items():
                if isinstance(value, str) and value.startswith("http"):
                    # 检测图片 URL
                    if any(ext in value.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                        if value not in images:
                            images.append(value)
                    # 检测视频 URL
                    elif any(ext in value.lower() for ext in ['.mp4', '.mov', '.avi', '.webm']):
                        if value not in videos:
                            videos.append(value)
                    # CloudFront 图片资源
                    elif 'resource.opencreator.io/images' in value:
                        if value not in images:
                            images.append(value)

        return {
            "images": images[:20],  # 限制每个工作流最多20张图片
            "videos": videos[:10],  # 限制每个工作流最多10个视频
            "texts": texts
        }

    def _format_workflow_for_prompt(self, rank: int, workflow: Dict, full_data: Optional[Dict]) -> str:
        """格式化单个工作流用于 prompt"""
        lines = []
        lines.append(f"### 工作流 {rank}")
        lines.append(f"- 名称: {workflow.get('workflow_name') or '未命名'}")
        lines.append(f"- 运行次数: {workflow.get('run_count', 0)}")
        lines.append(f"- 节点类型: {', '.join(workflow.get('node_types', []))}")
        lines.append(f"- 签名: {workflow.get('signature', '')}")

        if full_data:
            nodes = full_data.get("nodes", [])
            media = self._extract_media_urls(nodes)

            if media["texts"]:
                lines.append(f"- 用户输入文本:")
                for i, text in enumerate(media["texts"][:3], 1):
                    # 截断过长的文本
                    if len(text) > 200:
                        text = text[:200] + "..."
                    lines.append(f"  {i}. {text}")

            if media["images"]:
                lines.append(f"- 图片数量: {len(media['images'])}")

            if media["videos"]:
                lines.append(f"- 视频数量: {len(media['videos'])}")

        lines.append("")
        return "\n".join(lines)

    async def _download_image(self, url: str) -> Optional[Dict]:
        """下载图片并转换为 Gemini 可用格式"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "image/jpeg")
                    # 简化 content-type
                    if "jpeg" in content_type or "jpg" in content_type:
                        mime_type = "image/jpeg"
                    elif "png" in content_type:
                        mime_type = "image/png"
                    elif "gif" in content_type:
                        mime_type = "image/gif"
                    elif "webp" in content_type:
                        mime_type = "image/webp"
                    else:
                        mime_type = "image/jpeg"

                    return {
                        "mime_type": mime_type,
                        "data": base64.standard_b64encode(response.content).decode("utf-8")
                    }
        except Exception as e:
            print(f"      下载图片失败: {url[:50]}... - {e}")
        return None

    async def _call_gemini_with_media(
        self,
        prompt: str,
        image_urls: List[str],
        video_urls: List[str]
    ) -> Optional[Dict]:
        """
        调用 Gemini API 进行多模态分析

        Args:
            prompt: 文本 prompt
            image_urls: 图片 URL 列表
            video_urls: 视频 URL 列表（暂不处理，只记录数量）

        Returns:
            解析后的 JSON 响应
        """
        try:
            # 构建内容列表
            contents = []

            # 下载并添加图片
            if image_urls:
                print(f"      下载 {len(image_urls)} 张图片...")
                download_tasks = [self._download_image(url) for url in image_urls[:200]]
                images = await asyncio.gather(*download_tasks)

                for img_data in images:
                    if img_data:
                        contents.append(types.Part.from_bytes(
                            data=base64.standard_b64decode(img_data["data"]),
                            mime_type=img_data["mime_type"]
                        ))

                print(f"      成功加载 {len([i for i in images if i])} 张图片")

            # 添加文本 prompt（放在最后）
            contents.append(prompt)

            # 视频暂时只在 prompt 中说明数量，不实际传递
            # （Gemini 对视频 URL 的支持有限）

            # 调用 API
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=64000,
                )
            )

            # 记录 token 使用
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                self.total_input_tokens += response.usage_metadata.prompt_token_count or 0
                self.total_output_tokens += response.usage_metadata.candidates_token_count or 0

            # 解析 JSON 响应
            response_text = response.text.strip()

            # 尝试提取 JSON（可能被 markdown 包裹）
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                response_text = json_match.group(1)

            return json.loads(response_text)

        except json.JSONDecodeError as e:
            print(f"      JSON 解析失败: {e}")
            print(f"      原始响应: {response_text[:500]}...")
            return None
        except Exception as e:
            print(f"      Gemini API 调用失败: {e}")
            return None

    async def analyze_user(self, user_profile: Dict) -> str:
        """
        分析单个用户的画像

        Returns:
            处理结果: "success", "skip", "error: xxx"
        """
        async with self.semaphore:
            user_id = user_profile.get("user_id")
            user_email = user_profile.get("user_email", "unknown")

            try:
                print(f"\n处理用户: {user_email}")

                stats = user_profile.get("stats", {})
                top_workflows = user_profile.get("top_workflows", [])[:self.top_n]

                if not top_workflows:
                    print(f"  跳过: 没有工作流数据")
                    return "skip"

                # 收集所有工作流的完整数据和媒体
                workflows_text_parts = []
                all_images = []
                all_videos = []

                for i, workflow in enumerate(top_workflows, 1):
                    signature = workflow.get("signature", "")

                    # 获取完整工作流数据
                    full_data = await self.get_workflow_full_data(user_id, signature)

                    # 格式化工作流信息
                    workflow_text = self._format_workflow_for_prompt(i, workflow, full_data)
                    workflows_text_parts.append(workflow_text)

                    # 收集媒体 URL
                    if full_data:
                        media = self._extract_media_urls(full_data.get("nodes", []))
                        all_images.extend(media["images"])
                        all_videos.extend(media["videos"])

                # 构建完整 prompt
                prompt = ANALYSIS_PROMPT.format(
                    total_runs=stats.get("total_runs_30d", 0),
                    active_days=stats.get("active_days_30d", 0),
                    workflow_count=len(top_workflows),
                    workflows_text="\n".join(workflows_text_parts)
                )

                print(f"  工作流数: {len(top_workflows)}, 图片: {len(all_images)}, 视频: {len(all_videos)}")

                # 调用 Gemini API
                result = await self._call_gemini_with_media(
                    prompt,
                    all_images[:200],  # 限制总图片数
                    all_videos[:100]   # 限制总视频数
                )

                if not result:
                    print(f"  错误: AI 分析失败")
                    return "error: AI analysis failed"

                # 保存结果
                ai_profile = {
                    "user_category": result.get("user_category", "其他"),
                    "user_subcategory": result.get("user_subcategory", "无法判断"),
                    **result.get("user_profile", {}),
                    "positioning": result.get("positioning", {}),
                    "business_potential": result.get("business_potential", {}),
                    "workflow_analysis": result.get("workflow_analysis", []),
                    "analyzed_at": datetime.now(),
                    "model": "gemini-2.0-flash"
                }

                await self.profile_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "ai_profile": ai_profile,
                        "updated_at": datetime.now()
                    }}
                )

                print(f"  完成: {ai_profile.get('summary', 'N/A')}")
                return "success"

            except Exception as e:
                print(f"  错误: {e}")
                return f"error: {e}"

    async def run(self, specific_email: Optional[str] = None, force: bool = False):
        """运行主流程

        Args:
            specific_email: 只分析指定邮箱的用户
            force: 强制重新分析所有用户（覆盖已有画像）
        """
        print("=" * 60)
        print("AI 用户画像分析器")
        print(f"并发数: {self.concurrency}")
        print(f"Top 工作流数: {self.top_n}")
        if force:
            print("模式: 强制重新分析所有用户")
        print("=" * 60)

        # 1. 获取待分析用户
        print(f"\n[1/3] 获取待分析用户...")
        users = await self.get_users_to_analyze(specific_email, force=force)
        total_users = len(users)
        print(f"      找到 {total_users} 个用户待分析")

        if not users:
            print("没有找到需要分析的用户，退出。")
            return

        # 2. 并发分析
        print(f"\n[2/3] 开始 AI 分析...")

        tasks = [self.analyze_user(user) for user in users]

        results = []
        pbar = tqdm(total=len(tasks), desc="分析进度")

        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)

            # 更新进度条，显示实时 token 统计
            pbar.set_postfix({
                'input_tokens': f'{self.total_input_tokens:,}',
                'output_tokens': f'{self.total_output_tokens:,}',
                'cost': f'${(self.total_input_tokens * 0.50 + self.total_output_tokens * 3.00) / 1_000_000:.4f}'
            })
            pbar.update(1)

        pbar.close()

        # 统计结果
        for result in results:
            if result == "success":
                self.success_count += 1
            elif result == "skip":
                self.skip_count += 1
            else:
                self.error_count += 1

        # 3. 汇总
        print(f"\n[3/3] 完成!")
        print("=" * 60)
        print(f"总用户数: {total_users}")
        print(f"成功分析: {self.success_count}")
        print(f"跳过: {self.skip_count}")
        print(f"错误: {self.error_count}")
        print(f"\nToken 使用统计:")
        print(f"  输入 tokens: {self.total_input_tokens:,}")
        print(f"  输出 tokens: {self.total_output_tokens:,}")

        # 估算成本 (Gemini 3 Flash: $0.50/M input, $3.00/M output)
        input_cost = self.total_input_tokens * 0.50 / 1_000_000
        output_cost = self.total_output_tokens * 3.00 / 1_000_000
        print(f"  估算成本: ${input_cost + output_cost:.4f}")
        print("=" * 60)

    async def close(self):
        """关闭数据库连接"""
        self.mongo_client.close()


async def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="AI 用户画像分析器")
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=5,
        help="并发数，默认5"
    )
    parser.add_argument(
        "--email", "-e",
        type=str,
        default=None,
        help="只分析指定邮箱的用户"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="强制重新分析所有用户（覆盖已有画像）"
    )
    args = parser.parse_args()

    # 加载环境变量
    env_file = load_env()
    print(f"使用配置文件: {env_file}")

    analyzer = AIProfileAnalyzer(concurrency=args.concurrency)
    try:
        await analyzer.run(specific_email=args.email, force=args.force)
    finally:
        await analyzer.close()


if __name__ == "__main__":
    asyncio.run(main())
