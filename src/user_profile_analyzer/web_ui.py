"""
用户画像数据展示 Web UI (Gradio)

运行方式：
    cd user-profile-analyzer
    source .venv/bin/activate
    python -m src.user_profile_analyzer.web_ui

    # 正式环境
    APP_ENV=prod python -m src.user_profile_analyzer.web_ui
"""

import os
from pathlib import Path
from typing import List, Dict, Any

import gradio as gr
import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi


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


class UserProfileViewer:
    """用户画像数据查看器"""

    def __init__(self):
        mongo_uri = os.getenv("MONGO_ATLAS_URI")
        mongo_db = os.getenv("MONGO_DB")

        if not mongo_uri or not mongo_db:
            raise ValueError("请确保环境变量中配置了 MONGO_ATLAS_URI 和 MONGO_DB")

        self.client = MongoClient(mongo_uri, server_api=ServerApi('1'))
        self.db = self.client[mongo_db]
        self.collection = self.db["user_workflow_profile"]

    def get_all_profiles(self, sort_by: str = "total_runs_30d", order: str = "降序") -> pd.DataFrame:
        """获取所有用户画像数据"""
        sort_field = f"stats.{sort_by}" if sort_by in ["total_runs_30d", "active_days_30d"] else sort_by
        sort_order = -1 if order == "降序" else 1

        cursor = self.collection.find(
            {},
            {
                "_id": 0,
                "user_id": 1,
                "user_email": 1,
                "stats.total_runs_30d": 1,
                "stats.active_days_30d": 1,
                "top_workflows": 1,
                "created_at": 1
            }
        ).sort(sort_field, sort_order)

        data = []
        for doc in cursor:
            # 获取 Top 3 工作流签名
            top_workflows = doc.get("top_workflows", [])[:3]
            workflow_summary = " | ".join([
                f"{w.get('workflow_name') or w.get('signature', 'N/A')}({w.get('run_count', 0)}次)"
                for w in top_workflows
            ])

            data.append({
                "用户ID": doc.get("user_id", "")[:20] + "...",
                "邮箱": doc.get("user_email", ""),
                "30天运行次数": doc.get("stats", {}).get("total_runs_30d", 0),
                "30天活跃天数": doc.get("stats", {}).get("active_days_30d", 0),
                "Top工作流": workflow_summary,
            })

        return pd.DataFrame(data)

    def search_profiles(self, keyword: str, sort_by: str = "total_runs_30d", order: str = "降序") -> pd.DataFrame:
        """搜索用户画像"""
        if not keyword:
            return self.get_all_profiles(sort_by, order)

        sort_field = f"stats.{sort_by}" if sort_by in ["total_runs_30d", "active_days_30d"] else sort_by
        sort_order = -1 if order == "降序" else 1

        cursor = self.collection.find(
            {"user_email": {"$regex": keyword, "$options": "i"}},
            {
                "_id": 0,
                "user_id": 1,
                "user_email": 1,
                "stats.total_runs_30d": 1,
                "stats.active_days_30d": 1,
                "top_workflows": 1,
            }
        ).sort(sort_field, sort_order)

        data = []
        for doc in cursor:
            top_workflows = doc.get("top_workflows", [])[:3]
            workflow_summary = " | ".join([
                f"{w.get('workflow_name') or w.get('signature', 'N/A')}({w.get('run_count', 0)}次)"
                for w in top_workflows
            ])

            data.append({
                "用户ID": doc.get("user_id", "")[:20] + "...",
                "邮箱": doc.get("user_email", ""),
                "30天运行次数": doc.get("stats", {}).get("total_runs_30d", 0),
                "30天活跃天数": doc.get("stats", {}).get("active_days_30d", 0),
                "Top工作流": workflow_summary,
            })

        return pd.DataFrame(data)

    def get_user_detail(self, email: str) -> str:
        """获取用户详情"""
        if not email:
            return "请选择一个用户"

        doc = self.collection.find_one(
            {"user_email": email},
            {"_id": 0}
        )

        if not doc:
            return "未找到该用户"

        # 格式化输出
        output = f"""
## 用户信息
- **用户ID**: {doc.get('user_id', 'N/A')}
- **邮箱**: {doc.get('user_email', 'N/A')}
- **30天运行次数**: {doc.get('stats', {}).get('total_runs_30d', 0)}
- **30天活跃天数**: {doc.get('stats', {}).get('active_days_30d', 0)}

## Top 15 工作流
"""
        for w in doc.get("top_workflows", []):
            name = w.get('workflow_name') or w.get('signature', 'N/A')
            output += f"""
### #{w.get('rank', 'N/A')} {name}
- **运行次数**: {w.get('run_count', 0)}
- **节点类型**: {', '.join(w.get('node_types', []))}
- **签名**: `{w.get('signature', 'N/A')}`
"""
        return output

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_users = self.collection.count_documents({})

        pipeline = [
            {"$group": {
                "_id": None,
                "total_runs": {"$sum": "$stats.total_runs_30d"},
                "avg_runs": {"$avg": "$stats.total_runs_30d"},
                "max_runs": {"$max": "$stats.total_runs_30d"},
            }}
        ]
        stats = list(self.collection.aggregate(pipeline))

        if stats:
            return {
                "total_users": total_users,
                "total_runs": stats[0].get("total_runs", 0),
                "avg_runs": round(stats[0].get("avg_runs", 0), 2),
                "max_runs": stats[0].get("max_runs", 0),
            }
        return {"total_users": 0, "total_runs": 0, "avg_runs": 0, "max_runs": 0}


def create_ui():
    """创建 Gradio UI"""
    env_file = load_env()
    print(f"使用配置文件: {env_file}")

    viewer = UserProfileViewer()
    stats = viewer.get_stats()

    with gr.Blocks(title="用户画像分析系统", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 📊 用户画像分析系统")

        # 统计信息
        with gr.Row():
            gr.Markdown(f"**总用户数**: {stats['total_users']}")
            gr.Markdown(f"**总运行次数**: {stats['total_runs']}")
            gr.Markdown(f"**平均运行次数**: {stats['avg_runs']}")
            gr.Markdown(f"**最高运行次数**: {stats['max_runs']}")

        # 搜索和排序
        with gr.Row():
            search_input = gr.Textbox(
                label="🔍 搜索邮箱",
                placeholder="输入邮箱关键词...",
                scale=3
            )
            sort_by = gr.Dropdown(
                choices=["total_runs_30d", "active_days_30d"],
                value="total_runs_30d",
                label="排序字段",
                scale=1
            )
            sort_order = gr.Dropdown(
                choices=["降序", "升序"],
                value="降序",
                label="排序方式",
                scale=1
            )
            search_btn = gr.Button("搜索", scale=1)

        # 数据表格
        data_table = gr.Dataframe(
            value=viewer.get_all_profiles(),
            label="用户列表",
            interactive=False,
            wrap=True,
        )

        # 用户详情
        with gr.Row():
            email_input = gr.Textbox(
                label="输入邮箱查看详情",
                placeholder="输入完整邮箱地址...",
                scale=3
            )
            detail_btn = gr.Button("查看详情", scale=1)

        user_detail = gr.Markdown(label="用户详情")

        # 绑定事件
        def on_search(keyword, sort_field, order):
            return viewer.search_profiles(keyword, sort_field, order)

        search_btn.click(
            fn=on_search,
            inputs=[search_input, sort_by, sort_order],
            outputs=data_table
        )

        search_input.submit(
            fn=on_search,
            inputs=[search_input, sort_by, sort_order],
            outputs=data_table
        )

        sort_by.change(
            fn=on_search,
            inputs=[search_input, sort_by, sort_order],
            outputs=data_table
        )

        sort_order.change(
            fn=on_search,
            inputs=[search_input, sort_by, sort_order],
            outputs=data_table
        )

        detail_btn.click(
            fn=viewer.get_user_detail,
            inputs=email_input,
            outputs=user_detail
        )

        email_input.submit(
            fn=viewer.get_user_detail,
            inputs=email_input,
            outputs=user_detail
        )

    return demo


if __name__ == "__main__":
    demo = create_ui()
    demo.launch(
        server_name="0.0.0.0",  # 允许外部访问
        server_port=7860,
        share=False,  # 设为 True 可生成公网链接
    )
