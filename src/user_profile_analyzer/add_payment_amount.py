"""
添加用户支付金额字段脚本

功能：
1. 遍历 user_workflow_profile 中的每个用户
2. 通过 user_id 在 payments_v2 表中查询已支付总金额
3. 将支付金额写入 user_workflow_profile.stats.total_paid_amount

运行方式：
    cd user-profile-analyzer
    uv run python -m src.user_profile_analyzer.add_payment_amount

    # 使用生产环境
    APP_ENV=prod uv run python -m src.user_profile_analyzer.add_payment_amount

    # 带时间范围过滤
    APP_ENV=prod uv run python -m src.user_profile_analyzer.add_payment_amount --start-date 2025-10-01 --end-date 2026-01-27
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


class PaymentAmountUpdater:
    """支付金额更新器"""

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
        self.payments_collection = self.db["payments_v2"]
        self.profile_collection = self.db["user_workflow_profile"]

        # 时间范围
        self.start_date = start_date
        self.end_date = end_date

        # 统计
        self.success_count = 0
        self.skip_count = 0
        self.error_count = 0
        self.total_amount = 0

    async def get_user_paid_amount(self, user_id: str) -> int:
        """
        查询用户的已支付总金额（单位：分）

        Returns:
            total_paid_cents: 已支付总金额（分）
        """
        match_query = {
            "user_id": user_id,
            "payment_status": "paid"
        }

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
            {"$group": {"_id": None, "total_paid_cents": {"$sum": "$amount"}}}
        ]

        cursor = self.payments_collection.aggregate(pipeline)
        results = await cursor.to_list(length=1)

        if results and results[0].get("total_paid_cents"):
            return results[0]["total_paid_cents"]
        return 0

    async def update_user_payment_amount(self, profile: dict) -> str:
        """更新单个用户的支付金额"""
        user_id = profile.get("user_id")

        try:
            # 查询支付金额
            total_paid_cents = await self.get_user_paid_amount(user_id)
            total_paid_dollars = round(total_paid_cents / 100, 2)

            # 更新 user_workflow_profile
            await self.profile_collection.update_one(
                {"_id": profile["_id"]},
                {
                    "$set": {
                        "stats.total_paid_amount": total_paid_dollars,
                        "updated_at": datetime.now()
                    }
                }
            )

            self.total_amount += total_paid_cents
            return "success"

        except Exception as e:
            return f"error: {e}"

    async def run(self):
        """运行主流程"""
        print("=" * 60)
        print("用户支付金额更新器")
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

        # 2. 更新支付金额
        print(f"\n[2/2] 更新支付金额...")

        pbar = tqdm(total=total_users, desc="更新进度")

        for user in users:
            result = await self.update_user_payment_amount(user)

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
        print(f"总支付金额: ${self.total_amount / 100:,.2f}")
        print("=" * 60)

    async def close(self):
        """关闭数据库连接"""
        self.mongo_client.close()


async def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="用户支付金额更新器")
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

    updater = PaymentAmountUpdater(start_date=start_date, end_date=end_date)
    try:
        await updater.run()
    finally:
        await updater.close()


if __name__ == "__main__":
    asyncio.run(main())
