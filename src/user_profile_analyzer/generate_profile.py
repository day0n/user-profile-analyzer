"""
用户工作流画像数据生成脚本（并发版本）

功能：
1. 查询最近30天有运行记录的用户
2. 并发处理，统计每个用户运行最多的工作流（Top 15）
3. 生成用户画像数据写入 user_workflow_profile 集合

运行方式：
    cd user-profile-analyzer
    source .venv/bin/activate
    python -m src.user_profile_analyzer.generate_profile

    # 正式环境
    APP_ENV=prod python -m src.user_profile_analyzer.generate_profile

    # 自定义并发数
    python -m src.user_profile_analyzer.generate_profile -c 200
"""

import asyncio
import os
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi
from tqdm.asyncio import tqdm


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


class UserWorkflowProfileGenerator:
    """用户工作流画像生成器（并发版本）"""

    # 输入型节点类型
    INPUT_NODE_TYPES = ["textInput", "imageInput", "videoInput", "audioInput"]

    def __init__(self, concurrency: int = 400):
        """
        初始化生成器

        Args:
            concurrency: 并发数，默认400
        """
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
        self.flow_collection = self.db["flow"]
        self.flow_details_collection = self.db["flow_details"]
        self.user_collection = self.db["user"]
        self.profile_collection = self.db["user_workflow_profile"]

        # 配置 - 时间范围：2025年10月1日 - 2026年1月27日
        self.start_date = datetime(2025, 10, 1)
        self.end_date = datetime(2026, 1, 27, 23, 59, 59)
        self.top_n = 15  # Top 15 工作流
        self.concurrency = concurrency  # 并发数
        self.semaphore = asyncio.Semaphore(concurrency)

        # 统计
        self.success_count = 0
        self.skip_count = 0
        self.error_count = 0

    def generate_workflow_signature(self, nodes: List[Dict]) -> str:
        """
        根据节点类型生成工作流签名

        例如: "imageMaker:2,textInput:1,videoMaker:1"
        """
        if not nodes:
            return "empty"

        type_counts = defaultdict(int)
        for node in nodes:
            node_type = node.get("type", "unknown")
            type_counts[node_type] += 1

        # 按类型名排序，生成签名
        signature = ",".join(
            f"{k}:{v}" for k, v in sorted(type_counts.items())
        )
        return signature

    def extract_node_types(self, nodes: List[Dict]) -> List[str]:
        """提取节点类型列表"""
        if not nodes:
            return []
        return list(set(node.get("type", "unknown") for node in nodes))

    def clean_node_data(self, node: Dict) -> Dict:
        """
        清理节点数据，用于保存到数据库

        规则：
        - 输入型节点保留完整 data，但剔除 results/model_options
        - 非输入节点只保留关键字段（prompt/模型/语音/比例）
        """
        node_type = node.get("type", "unknown")
        node_data = node.get("data", {})

        cleaned_node = {
            "id": node.get("id"),
            "type": node_type,
            "label": node_data.get("label"),
            "isInputNode": node_type in self.INPUT_NODE_TYPES,
        }

        if node_type in self.INPUT_NODE_TYPES:
            # 输入节点：保留全部 data，但剔除 results / model_options
            cleaned_data = {
                k: v for k, v in node_data.items()
                if k not in ["results", "model_options"]
            }
            cleaned_node["data"] = cleaned_data
        else:
            # 非输入节点：只保留关键字段
            cleaned_node["data"] = {
                "prompt": node_data.get("inputText"),
                "selectedModels": node_data.get("selectedModels"),
                "selectedVoice": node_data.get("selectedVoice"),
                "aspectRatio": node_data.get("aspectRatio"),
            }

        return cleaned_node

    def clean_edge_data(self, edge: Dict) -> Dict:
        """清理边数据"""
        return {
            "id": edge.get("id"),
            "source": edge.get("source"),
            "target": edge.get("target"),
            "sourceHandle": edge.get("sourceHandle"),
            "targetHandle": edge.get("targetHandle"),
        }

    def clean_workflow_topology(self, nodes: List[Dict], edges: List[Dict]) -> Dict:
        """
        清理工作流拓扑数据，用于保存到数据库

        返回清理后的 nodes 和 edges
        """
        cleaned_nodes = [self.clean_node_data(node) for node in (nodes or [])]
        cleaned_edges = [self.clean_edge_data(edge) for edge in (edges or [])]

        return {
            "nodes": cleaned_nodes,
            "edges": cleaned_edges,
        }

    async def get_users_with_runs_in_range(self) -> List[str]:
        """获取指定时间范围内有运行记录的用户ID列表"""
        pipeline = [
            {"$match": {"created_at": {"$gte": self.start_date, "$lte": self.end_date}}},
            {"$group": {"_id": "$user_id"}},
        ]

        cursor = self.flow_task_collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        return [r["_id"] for r in results if r["_id"]]

    async def get_user_email(self, user_id: str) -> Optional[str]:
        """获取用户邮箱"""
        user = await self.user_collection.find_one(
            {"user_id": user_id},
            {"user_email": 1}
        )
        return user.get("user_email") if user else None

    async def get_user_flow_tasks(self, user_id: str) -> List[Dict]:
        """获取用户在指定时间范围内的所有运行记录"""
        cursor = self.flow_task_collection.find(
            {
                "user_id": user_id,
                "created_at": {"$gte": self.start_date, "$lte": self.end_date}
            },
            {
                "_id": 0,
                "flow_task_id": 1,
                "nodes": 1,
                "edges": 1,
                "status": 1,
                "cost": 1,
                "created_at": 1
            }
        )
        return await cursor.to_list(length=None)

    async def find_matching_flow(self, signature: str, user_id: str) -> Dict:
        """
        尝试从 flow 表找到匹配的工作流，获取名称和快照

        匹配策略：找节点类型组合相同的工作流
        """
        # 获取用户的所有工作流
        cursor = self.flow_collection.find(
            {"user_id": user_id},
            {"flow_id": 1, "nodes": 1}
        )
        flows = await cursor.to_list(length=100)  # 限制查询数量

        # 找签名匹配的工作流
        for flow in flows:
            flow_sig = self.generate_workflow_signature(flow.get("nodes", []))
            if flow_sig == signature:
                # 找到匹配，获取详情
                flow_id = flow.get("flow_id")
                details = await self.flow_details_collection.find_one(
                    {"flow_id": flow_id},
                    {"project_name": 1, "snapshot": 1}
                )
                if details:
                    return {
                        "flow_id": flow_id,
                        "workflow_name": details.get("project_name", ""),
                        "snapshot_url": details.get("snapshot", {}).get("snapshot_url") if details.get("snapshot") else None
                    }

        # 没找到匹配，返回空
        return {
            "flow_id": None,
            "workflow_name": None,
            "snapshot_url": None
        }

    async def generate_user_profile(self, user_id: str) -> Optional[Dict]:
        """生成单个用户的画像数据"""
        # 获取用户邮箱
        user_email = await self.get_user_email(user_id)
        if not user_email:
            return None

        # 获取运行记录
        flow_tasks = await self.get_user_flow_tasks(user_id)
        if not flow_tasks:
            return None

        # 统计活跃天数
        active_days = len(set(
            task["created_at"].date()
            for task in flow_tasks
            if task.get("created_at")
        ))

        # 按签名聚合工作流
        workflow_stats = defaultdict(lambda: {
            "count": 0,
            "sample_nodes": None,
            "sample_edges": None,
            "node_types": [],
            "flow_task_id": None
        })

        for task in flow_tasks:
            nodes = task.get("nodes", [])
            edges = task.get("edges", [])
            signature = self.generate_workflow_signature(nodes)

            workflow_stats[signature]["count"] += 1
            if workflow_stats[signature]["sample_nodes"] is None:
                workflow_stats[signature]["sample_nodes"] = nodes
                workflow_stats[signature]["sample_edges"] = edges
                workflow_stats[signature]["node_types"] = self.extract_node_types(nodes)
                workflow_stats[signature]["flow_task_id"] = task.get("flow_task_id")

        # 按运行次数排序，取 Top N
        sorted_workflows = sorted(
            workflow_stats.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:self.top_n]

        # 构建 top_workflows 列表
        top_workflows = []
        for rank, (signature, stats) in enumerate(sorted_workflows, 1):
            # 尝试匹配工作流获取名称和快照
            flow_info = await self.find_matching_flow(signature, user_id)

            # 清理工作流拓扑数据
            topology = self.clean_workflow_topology(
                stats["sample_nodes"],
                stats["sample_edges"]
            )

            top_workflows.append({
                "rank": rank,
                "flow_id": flow_info["flow_id"],
                "flow_task_id": stats["flow_task_id"],
                "workflow_name": flow_info["workflow_name"],
                "signature": signature,
                "run_count": stats["count"],
                "node_types": stats["node_types"],
                "snapshot_url": flow_info["snapshot_url"],
                # 完整的工作流拓扑结构
                "topology": topology,
            })

        # 构建用户画像文档
        profile = {
            "user_id": user_id,
            "user_email": user_email,
            "stats": {
                "total_runs": len(flow_tasks),
                "active_days": active_days,
                "period": "2024-10-01 ~ 2025-01-27"
            },
            "top_workflows": top_workflows,
            "ai_profile": None,  # 后续 AI 分析填充
            "payment_stats": None,  # 后续付费统计填充
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }

        return profile

    async def save_profile(self, profile: Dict):
        """保存用户画像到数据库（upsert）"""
        await self.profile_collection.update_one(
            {"user_id": profile["user_id"]},
            {"$set": profile},
            upsert=True
        )

    async def process_user(self, user_id: str) -> str:
        """
        处理单个用户（带信号量控制）

        Returns:
            处理结果: "success", "skip", "error"
        """
        async with self.semaphore:
            try:
                profile = await self.generate_user_profile(user_id)
                if profile:
                    await self.save_profile(profile)
                    return "success"
                else:
                    return "skip"
            except Exception as e:
                return f"error: {e}"

    async def run(self):
        """运行主流程"""
        print("=" * 60)
        print("用户工作流画像生成器（并发版本）")
        print(f"并发数: {self.concurrency}")
        print("=" * 60)

        # 1. 获取有运行记录的用户
        print(f"\n[1/3] 查询 {self.start_date.strftime('%Y-%m-%d')} ~ {self.end_date.strftime('%Y-%m-%d')} 有运行记录的用户...")
        user_ids = await self.get_users_with_runs_in_range()
        total_users = len(user_ids)
        print(f"      找到 {total_users} 个用户")

        if not user_ids:
            print("没有找到符合条件的用户，退出。")
            return

        # 2. 并发处理用户
        print(f"\n[2/3] 并发生成用户画像...")

        # 创建所有任务
        tasks = [self.process_user(user_id) for user_id in user_ids]

        # 使用 tqdm 显示进度条并执行
        results = []
        for coro in tqdm.as_completed(tasks, total=len(tasks), desc="处理进度"):
            result = await coro
            results.append(result)

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
        print(f"成功处理: {self.success_count}")
        print(f"跳过: {self.skip_count}")
        print(f"错误: {self.error_count}")
        print(f"数据已写入集合: user_workflow_profile")
        print("=" * 60)

    async def close(self):
        """关闭数据库连接"""
        self.mongo_client.close()


async def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="用户工作流画像生成器")
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=400,
        help="并发数，默认400"
    )
    args = parser.parse_args()

    # 加载环境变量
    env_file = load_env()
    print(f"使用配置文件: {env_file}")

    generator = UserWorkflowProfileGenerator(concurrency=args.concurrency)
    try:
        await generator.run()
    finally:
        await generator.close()


if __name__ == "__main__":
    asyncio.run(main())
