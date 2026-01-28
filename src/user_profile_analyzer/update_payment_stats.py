"""
更新用户支付统计脚本

功能：
1. 遍历 user_workflow_profile 中的每个用户
2. 通过 user_id 在 order 表中查询订单统计
3. 统计 paid/unpaid 订单数量和金额
4. 将统计结果写入 user_workflow_profile.payment_stats

运行方式：
    cd user-profile-analyzer
    uv run python -m src.user_profile_analyzer.update_payment_stats

    # 使用生产环境
    APP_ENV=prod uv run python -m src.user_profile_analyzer.update_payment_stats

    # 带时间范围过滤
    APP_ENV=prod uv run python -m src.user_profile_analyzer.update_payment_stats --start-date 2025-10-01 --end-date 2026-01-27
"""

import asyncio
import os
import argparse
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
    """支付统计更新器"""

    def __init__(self, start_date: datetime = None, end_date: datetime = None):
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
        self.order_collection = self.db["order"]
        self.profile_collection = self.db["user_workflow_profile"]

        # 时间范围
        self.start_date = start_date
        self.end_date = end_date

        # 统计
        self.success_count = 0
        self.skip_count = 0
        self.error_count = 0

    async def get_user_order_stats(self, user_id: str) -> dict:
        """
        查询用户的订单统计

        Returns:
            {
                "paid_count": int,
                "unpaid_count": int,
                "paid_amount": float,  # 美元
                "unpaid_amount": float  # 美元
            }
        """
        match_query = {"user_id": user_id}

        # 如果有时间范围，添加时间过滤
        if self.start_date or self.end_date:
            date_filter = {}
            if self.start_date:
                date_filter["$gte"] = self.start_date
            if self.end_date:
                date_filter["$lte"] = self.end_date
            if date_filter:
                match_query["created_at"] = date_filter

        pipeline = [
            {"$match": match_query},
            {
                "$group": {
                    "_id": "$pay_status",
                    "count": {"$sum": 1},
                    "total_amount": {"$sum": "$amount"}
                }
            }
        ]

        cursor = self.order_collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)

        # 初始化统计
        stats = {
            "paid_count": 0,
            "unpaid_count": 0,
            "paid_amount": 0.0,
            "unpaid_amount": 0.0
        }

        # 解析聚合结果
        for item in results:
            status = item.get("_id")
            count = item.get("count", 0)
            amount_cents = item.get("total_amount", 0)
            amount_usd = round(amount_cents / 100, 2)

            if status == "paid":
                stats["paid_count"] = count
                stats["paid_amount"] = amount_usd
            elif status == "unpaid":
                stats["unpaid_count"] = count
                stats["unpaid_amount"] = amount_usd

        return stats

    async def update_user_payment_stats(self, profile: dict) -> str:
        """更新单个用户的支付统计"""
        user_id = profile.get("user_id")

        try:
            # 查询订单统计
            stats = await self.get_user_order_stats(user_id)

            # 更新 user_workflow_profile
            await self.profile_collection.update_one(
                {"_id": profile["_id"]},
                {
                    "$set": {
                        "payment_stats": {
                            "paid_count": stats["paid_count"],
                            "unpaid_count": stats["unpaid_count"],
                            "paid_amount": stats["paid_amount"],
                            "unpaid_amount": stats["unpaid_amount"],
                            "updated_at": datetime.now()
                        }
                    }
                }
            )

            return "success"

        except Exception as e:
            return f"error: {e}"

    async def run(self):
        """运行主流程"""
        print("=" * 60)
        print("用户支付统计更新器")
        if self.start_date or self.end_date:
            print(f"时间范围: {self.start_date} ~ {self.end_date}")
        else:
            print("时间范围: 全部")
        print("=" * 60)

        # 1. 获取所有用户
        print("\n[1/2] 获取用户列表...")
        cursor = self.profile_collection.find(
            {},
            {"_id": 1, "user_id": 1}
        )
        users = await cursor.to_list(length=None)
        total_users = len(users)
        print(f"      找到 {total_users} 个用户")

        if not users:
            print("没有找到用户，退出。")
            return

        # 2. 更新支付统计
        print(f"\n[2/2] 更新支付统计...")

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
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="用户支付统计更新器")
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="开始日期，格式：YYYY-MM-DD"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="结束日期，格式：YYYY-MM-DD"
    )
    args = parser.parse_args()

    # 解析日期
    start_date = None
    end_date = None

    if args.start_date:
        start_date = datetime.fromisoformat(f"{args.start_date}T00:00:00")
    if args.end_date:
        end_date = datetime.fromisoformat(f"{args.end_date}T23:59:59")

    # 加载环境变量
    env_file = load_env()
    print(f"使用配置文件: {env_file}")

    updater = PaymentStatsUpdater(start_date=start_date, end_date=end_date)
    try:
        await updater.run()
    finally:
        await updater.close()


if __name__ == "__main__":
    asyncio.run(main())
