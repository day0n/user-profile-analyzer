"""
添加用户付费统计字段脚本 (高性能版)

功能：
1. 一次性聚合 payments_v2 表，获取所有用户的 paid/unpaid 统计
2. 批量写入 user_workflow_profile
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
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
        self.payments_v2_collection = self.db["payments_v2"]
        self.profile_collection = self.db["user_workflow_profile"]

    async def run(self):
        """运行主流程"""
        print("=" * 60)
        print("用户付费统计更新器 (高性能版)")
        print("=" * 60)

        # 1. 聚合所有支付数据
        print("\n[1/3] 聚合 payments_v2 数据...")
        pipeline = [
            {"$match": {"payment_status": {"$in": ["paid", "unpaid"]}}},
            {
                "$group": {
                    "_id": {
                        "user_id": "$user_id", 
                        "status": "$payment_status"
                    }, 
                    "count": {"$sum": 1},
                    "total_amount": {"$sum": "$amount"}
                }
            }
        ]
        
        cursor = self.payments_v2_collection.aggregate(pipeline)
        
        # 内存中整理数据: user_id -> stats
        user_stats_map = {}
        
        async for doc in cursor:
            uid = doc["_id"].get("user_id")
            if not uid: continue
            
            status = doc["_id"].get("status")
            count = doc["count"]
            amount = doc.get("total_amount", 0) # cents
            
            if uid not in user_stats_map:
                user_stats_map[uid] = {"paid": 0, "unpaid": 0, "paid_amount_cents": 0}
            
            if status == "paid":
                user_stats_map[uid]["paid"] = count
                user_stats_map[uid]["paid_amount_cents"] = amount
            elif status == "unpaid":
                user_stats_map[uid]["unpaid"] = count

        print(f"      统计到 {len(user_stats_map)} 个有支付记录的用户")

        # 2. 准备批量更新操作
        print("\n[2/3] 准备 Bulk Write 操作...")
        
        # 获取所有 Profile 的 user_id
        profiles_cursor = self.profile_collection.find({}, {"_id": 1, "user_id": 1})
        bulk_ops = []
        updated_count = 0
        
        async for profile in profiles_cursor:
            uid = profile.get("user_id")
            if not uid: continue
            
            stats = user_stats_map.get(uid, {"paid": 0, "unpaid": 0, "paid_amount_cents": 0})
            
            paid_count = stats["paid"]
            unpaid_count = stats["unpaid"]
            total_paid_usd = round(stats["paid_amount_cents"] / 100, 2)
            
            # Logic Update: Intent = Unpaid > 0 AND Paid == 0
            is_paid_user = paid_count > 0
            has_payment_intent = (paid_count == 0) and (unpaid_count > 0)
            
            update_data = {
                "stats.total_paid_usd": total_paid_usd,
                "payment_stats": {
                    "paid_count": paid_count,
                    "unpaid_count": unpaid_count,
                    "is_paid_user": is_paid_user,
                    "has_payment_intent": has_payment_intent,
                    "updated_at": datetime.now()
                }
            }
            
            bulk_ops.append(UpdateOne({"_id": profile["_id"]}, {"$set": update_data}))
            
        print(f"      准备更新 {len(bulk_ops)} 个用户画像")
            
        # 3. 执行批量写入
        print("\n[3/3] 执行 Bulk Write (可能需要几秒钟)...")
        if bulk_ops:
            # 分批写入，每批 1000 条，避免单次包过大
            batch_size = 1000
            total_modified = 0
            
            for i in tqdm(range(0, len(bulk_ops), batch_size), desc="Writing Batch"):
                batch = bulk_ops[i:i + batch_size]
                result = await self.profile_collection.bulk_write(batch)
                total_modified += result.modified_count
                
            print(f"\n完成! 实际修改了 {total_modified} 个文档。")
        else:
            print("没有数据需要更新。")

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
