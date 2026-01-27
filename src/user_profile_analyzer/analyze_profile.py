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
- 30天运行次数：{total_runs_30d}
- 30天活跃天数：{active_days_30d}

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

## 7大用户分类（user_category）

**重要：必须从以下7个分类中选择1个，不能组合，不能自创！**

### 1. 电商上架转化
**核心本质：** 为电商平台商品上架准备的静态展示素材，目的是让买家看清商品细节、促进下单。
- 输出形态：以图片为主（而非视频）
- 使用场景：商品在电商平台的展示页面（主图、详情页、SKU 对比等）
- 用户意图：让商品"上架"、"展示"、优化"listing"
- 典型例子：淘宝主图、亚马逊 listing 图、产品对比图、白底图
- **判断思路：** 用户在为电商平台准备商品展示图片

### 2. 电商营销投放
**核心本质：** 为了在社交媒体或电商平台投放广告、带货，制作的视频素材，目的是吸引流量、促进转化。
- 输出形态：以视频为主
- 使用场景：社交媒体广告投放、直播带货、短视频营销
- 用户意图：投放广告、带货、种草、获取流量和转化
- 典型例子：TikTok 广告视频、抖音带货视频、Instagram 推广视频
- **判断思路：** 用户在制作用于投放和带货的视频广告

### 3. 品牌/商业广告
**核心本质：** 为品牌形象宣传、企业传播制作的高质量内容，目的是提升品牌认知而非直接销售转化。
- 输出形态：高质量视频或图片
- 使用场景：品牌宣传、企业形象传播、品牌故事讲述
- 用户意图：提升品牌认知、传递品牌价值、塑造品牌形象
- 典型例子：品牌 TVC、企业宣传片、品牌海报、形象片
- **与影视创作的区别：** 有明确的商业品牌露出和投放意图
- **判断思路：** 用户在为品牌做形象宣传，而不是直接卖货

### 4. 设备内容
**核心本质：** 真人出镜展示和讲解设备/产品，目的是测评、演示、教学。
- 输出形态：视频，真人出镜
- 使用场景：产品测评、开箱视频、使用教程、产品对比
- 用户意图：展示设备使用、评测产品、教学演示
- 典型例子：KOL 测评视频、开箱视频、产品使用教程
- **关键特征：** 真人 + 设备/产品明确露出 + 讲解/演示
- **判断思路：** 用户在制作真人出镜的设备测评或教程内容

### 5. 影视创作
**核心本质：** 强调叙事性、艺术性、镜头语言的内容创作，目的是讲故事、表达创意，而非商业广告。
- 输出形态：视频或创意图片
- 使用场景：短剧、微电影、MV、海报、logo、动画
- 用户意图：讲故事、艺术创作、内容创作
- 典型例子：短剧、音乐视频、电影海报、logo 设计
- **与品牌广告的区别：** 无明确商业投放意图，强调叙事和艺术表达
- **判断思路：** 用户在创作有叙事性和艺术性的影视内容

### 6. 个人兴趣/非商业
**核心本质：** 个人娱乐、兴趣爱好、非商业目的的使用。
- 输出形态：各种形式
- 使用场景：个人照片美化、表情包、头像、壁纸、艺术创作
- 用户意图：个人使用、娱乐、兴趣爱好
- 典型例子：个人照片处理、表情包制作、头像生成
- **关键特征：** 无商业意图，纯个人使用
- **判断思路：** 用户在为个人兴趣和娱乐使用平台

### 7. 其他
**核心本质：** 无法归入以上6类的内容，或内容过于分散无法判断。

## 分类优先级（当用户同时符合多个特征时）
电商上架转化 > 电商营销投放 > 品牌/商业广告 > 设备内容 > 影视创作 > 个人兴趣/非商业 > 其他

## 分析要求

1. **分析每个工作流的目的**：
   - 理解用户的真实意图（不要机械匹配关键词）
   - 从输出形态（图/视频）、内容特征、使用场景综合判断
   - 判断属于上述7大类中的哪一类

2. **精准用户定位**：
   - 用户所属行业（从图片内容、文案关键词推断）
   - 用户的业务规模（从使用频率、内容复杂度推断）
   - 用户主要发布的平台（从内容格式、风格推断）
   - 用户制作的内容类型

3. **评估商业价值潜力**：
   - 评估用户当前阶段（尝试期、成长期、成熟期、流失期）
   - 分析可能阻碍用户继续使用的因素
   - 给出针对性的运营建议

## 输出格式（JSON）
{{
  "workflow_analysis": [
    {{
      "rank": 1,
      "category": "工作流所属分类（7大类之一）",
      "purpose": "工作流目的描述",
      "confidence": "高/中/低",
      "reason": "判断理由（简短，说明为什么属于这个分类）"
    }}
  ],
  "user_category": "【必须从7大类中选择1个】电商上架转化 | 电商营销投放 | 品牌/商业广告 | 设备内容 | 影视创作 | 个人兴趣/非商业 | 其他",
  "user_profile": {{
    "primary_purpose": "用户主要使用目的",
    "user_type": "用户类型标签（如：电商卖家/内容创作者/营销人员/KOL/影视创作者/个人用户）",
    "activity_level": "高频活跃/中等活跃/轻度使用",
    "content_focus": ["内容偏好1", "内容偏好2"],
    "tags": ["标签1", "标签2", "标签3"],
    "summary": "一句话总结用户画像（30字内）"
  }},
  "positioning": {{
    "industry": "具体行业（服装/美妆/食品/3C数码/家居/教育/游戏/汽车/房产/金融/医疗健康/旅游/餐饮/母婴/宠物/运动健身/无法判断）",
    "business_scale": "业务规模（个人卖家/小型团队/中型企业/大型品牌/无法判断）",
    "platform": "主要平台（抖音/快手/小红书/淘宝/拼多多/京东/跨境电商/微信视频号/B站/YouTube/无法判断）",
    "content_type": "内容类型（商品展示图/商品展示视频/种草图文/品牌广告/短剧/口播视频/教程内容/娱乐内容/无法判断）"
  }},
  "business_potential": {{
    "score": 8,
    "stage": "尝试期/成长期/成熟期/流失期",
    "barrier": "可能的阻碍因素（如：不熟悉操作、找不到合适模板、效果不满意、价格顾虑等）",
    "recommendation": "运营建议（如：推荐行业模板、提供1对1指导、发送使用教程等）"
  }}
}}

## 商业潜力评分标准（score 1-10）
- 9-10分：明确的商业需求（电商产品图/视频、品牌广告），使用频率低但有持续潜力
- 7-8分：有商业倾向（营销内容、带货素材），处于尝试或成长期
- 5-6分：可能有商业需求但不明确，需要进一步观察
- 3-4分：偏向个人使用，商业价值较低
- 1-2分：纯粹个人娱乐或测试，无商业价值

## 定位判断指南
- **行业判断**：从图片内容（产品类型）、文案关键词（品牌词、产品词）推断
- **规模判断**：个人卖家（简单素材、低频使用）、小型团队（多样化内容、中频使用）、中大型企业（品牌化内容、高频批量）
- **平台判断**：竖版视频（抖音/快手）、方形图文（小红书）、横版视频（B站/YouTube）、商品主图（电商平台）
- **如果信息不足无法判断，填写"无法判断"，不要猜测**

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

        # 配置
        self.days_range = 30
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
        cutoff_date = datetime.now() - timedelta(days=self.days_range)

        # 查找该用户最近30天的任务，找到签名匹配的
        cursor = self.flow_task_collection.find(
            {
                "user_id": user_id,
                "created_at": {"$gte": cutoff_date},
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
                    total_runs_30d=stats.get("total_runs_30d", 0),
                    active_days_30d=stats.get("active_days_30d", 0),
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
