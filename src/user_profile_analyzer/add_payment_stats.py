"""
添加用户付费统计字段脚本

功能：
1. 遍历 user_workflow_profile 中的每个用户
2. 通过 email 在 user 表中查找 user_id
3. 用 user_id 在 order 表中统计 paid 和 unpaid 的数量
4. 将付费统计数据写回 user_workflow_profile

运行方式：
    cd user-profile-analyzer
    uv run python -m src.user_profile_analyzer.add_payment_stats

    # 使用生产环境
    APP_ENV=prod uv run python -m src.user_profile_analyzer.add_payment_stats
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi
from tqdm import tqdm


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


class PaymentStatsUpdater:
    """付费统计更新器"""

    def __init__(self):
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
        self.user_collection = self.db["user"]
        self.order_collection = self.db["order"]
        self.profile_collection = self.db["user_workflow_profile"]

        # 统计
        self.success_count = 0
        self.skip_count = 0
        self.error_count = 0

    async def get_user_id_by_email(self, email: str) -> str | None:
        """通过 email 查找 user_id"""
        user = await self.user_collection.find_one(
            {"user_email": email},
            {"user_id": 1}
        )
        if user:
            return user.get("user_id")
        return None

    async def get_payment_stats(self, user_id: str) -> dict:
        """统计用户的 paid 和 unpaid 订单数量"""
        pipeline = [
            {"$match": {"user_id": user_id, "pay_status": {"$in": ["paid", "unpaid"]}}},
            {"$group": {"_id": "$pay_status", "count": {"$sum": 1}}}
        ]

        cursor = self.order_collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)

        stats = {"paid_count": 0, "unpaid_count": 0}
        for item in results:
            if item["_id"] == "paid":
                stats["paid_count"] = item["count"]
            elif item["_id"] == "unpaid":
                stats["unpaid_count"] = item["count"]

        return stats

    async def update_user_payment_stats(self, profile: dict) -> str:
        """更新单个用户的付费统计"""
        user_email = profile.get("user_email")
        profile_user_id = profile.get("user_id")

        try:
            # 1. 通过 email 查找 user_id
            user_id = await self.get_user_id_by_email(user_email)

            if not user_id:
                # 如果通过 email 找不到，尝试使用 profile 中的 user_id
                user_id = profile_user_id

            if not user_id:
                return "skip: no user_id"

            # 2. 统计付费数据
            payment_stats = await self.get_payment_stats(user_id)

            # 3. 计算付费状态
            is_paid_user = payment_stats["paid_count"] > 0
            has_payment_intent = payment_stats["unpaid_count"] > 0

            # 4. 更新 user_workflow_profile
            update_data = {
                "payment_stats": {
                    "paid_count": payment_stats["paid_count"],
                    "unpaid_count": payment_stats["unpaid_count"],
                    "is_paid_user": is_paid_user,
                    "has_payment_intent": has_payment_intent,
                    "updated_at": datetime.now()
                },
                "updated_at": datetime.now()
            }

            await self.profile_collection.update_one(
                {"_id": profile["_id"]},
                {"$set": update_data}
            )

            return "success"

        except Exception as e:
            return f"error: {e}"

    async def run(self):
        """运行主流程"""
        print("=" * 60)
        print("用户付费统计更新器")
        print("=" * 60)

        # 1. 获取所有用户
        print("\n[1/2] 获取用户列表...")
        cursor = self.profile_collection.find(
            {},
            {"_id": 1, "user_id": 1, "user_email": 1}
        )
        users = await cursor.to_list(length=None)
        total_users = len(users)
        print(f"      找到 {total_users} 个用户")

        if not users:
            print("没有找到用户，退出。")
            return

        # 2. 更新付费统计
        print(f"\n[2/2] 更新付费统计...")

        pbar = tqdm(total=total_users, desc="更新进度")

        for user in users:
            result = await self.update_user_payment_stats(user)

            if result == "success":
                self.success_count += 1
            elif result.startswith("skip"):
                self.skip_count += 1
            else:
                self.error_count += 1

            pbar.update(1)

        pbar.close()

        # 3. 汇总
        print(f"\n完成!")
        print("=" * 60)
        print(f"总用户数: {total_users}")
        print(f"成功更新: {self.success_count}")
        print(f"跳过: {self.skip_count}")
        print(f"错误: {self.error_count}")
        print("=" * 60)

    async def close(self):
        """关闭数据库连接"""
        self.mongo_client.close()


async def main():
    # 加载环境变量
    env_file = load_env()
    print(f"使用配置文件: {env_file}")

    updater = PaymentStatsUpdater()
    try:
        await updater.run()
    finally:
        await updater.close()


if __name__ == "__main__":
    asyncio.run(main())
