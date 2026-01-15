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

    def get_user_inputs(self, email: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取用户的所有输入数据（分页）

        Args:
            email: 用户邮箱
            page: 页码（从1开始）
            page_size: 每页数量

        Returns:
            包含输入数据列表和分页信息的字典
        """
        if not email:
            return {"inputs": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

        # 获取用户ID
        user_doc = self.collection.find_one(
            {"user_email": email},
            {"user_id": 1}
        )

        if not user_doc:
            return {"inputs": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

        user_id = user_doc.get("user_id")

        # 从 flow_task 集合获取用户的所有任务
        flow_task_collection = self.db["flow_task"]

        # 计算总数
        total_tasks = flow_task_collection.count_documents({"user_id": user_id})
        total_pages = (total_tasks + page_size - 1) // page_size  # 向上取整

        # 分页查询
        skip = (page - 1) * page_size
        cursor = flow_task_collection.find(
            {"user_id": user_id},
            {
                "flow_task_id": 1,
                "nodes": 1,
                "created_at": 1,
                "status": 1
            }
        ).sort("created_at", -1).skip(skip).limit(page_size)

        inputs = []
        for task in cursor:
            task_id = task.get("flow_task_id", "")
            created_at = task.get("created_at", "")
            status = task.get("status", "")

            # 提取节点中的输入数据
            for node in task.get("nodes", []):
                node_type = node.get("type", "")
                data = node.get("data", {})

                # 只关注输入节点
                if node_type in ["imageInput", "textInput"]:
                    input_text = data.get("inputText", "")
                    image_base64 = data.get("imageBase64", "")

                    # 只添加有实际内容的输入
                    if input_text or (image_base64 and len(image_base64) > 100):
                        inputs.append({
                            "task_id": task_id,
                            "created_at": created_at,
                            "status": status,
                            "node_type": node_type,
                            "input_text": input_text,
                            "has_image": bool(image_base64 and len(image_base64) > 100),
                            "image_base64": image_base64 if image_base64 and len(image_base64) > 100 else ""
                        })

        return {
            "inputs": inputs,
            "total": total_tasks,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }

    def get_users_with_preview(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取用户列表和输入预览（按30天运行次数排序）

        Args:
            page: 页码（从1开始）
            page_size: 每页用户数量

        Returns:
            包含用户列表和分页信息的字典
        """
        # 计算总数
        total_users = self.collection.count_documents({})
        total_pages = (total_users + page_size - 1) // page_size

        # 分页查询用户
        skip = (page - 1) * page_size
        cursor = self.collection.find(
            {},
            {
                "user_id": 1,
                "user_email": 1,
                "stats.total_runs_30d": 1,
                "stats.active_days_30d": 1,
            }
        ).sort("stats.total_runs_30d", -1).skip(skip).limit(page_size)

        users = []
        flow_task_collection = self.db["flow_task"]

        for doc in cursor:
            user_id = doc.get("user_id", "")
            email = doc.get("user_email", "")
            runs_30d = doc.get("stats", {}).get("total_runs_30d", 0)
            active_days_30d = doc.get("stats", {}).get("active_days_30d", 0)

            # 获取该用户最近3条输入预览
            preview_cursor = flow_task_collection.find(
                {"user_id": user_id},
                {"nodes": 1, "created_at": 1, "status": 1}
            ).sort("created_at", -1).limit(3)

            previews = []
            for task in preview_cursor:
                for node in task.get("nodes", []):
                    node_type = node.get("type", "")
                    data = node.get("data", {})

                    if node_type in ["imageInput", "textInput"]:
                        input_text = data.get("inputText", "")
                        image_base64 = data.get("imageBase64", "")

                        if input_text or (image_base64 and len(image_base64) > 100):
                            previews.append({
                                "created_at": task.get("created_at", ""),
                                "node_type": node_type,
                                "input_text": input_text[:200] + "..." if len(input_text) > 200 else input_text,
                                "has_image": bool(image_base64 and len(image_base64) > 100),
                                "image_base64": image_base64 if image_base64 and len(image_base64) > 100 else ""
                            })
                            if len(previews) >= 3:
                                break
                    if len(previews) >= 3:
                        break

            users.append({
                "user_id": user_id,
                "email": email,
                "runs_30d": runs_30d,
                "active_days_30d": active_days_30d,
                "previews": previews
            })

        return {
            "users": users,
            "total": total_users,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }


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

        # 使用 Tabs 创建多个标签页
        with gr.Tabs():
            # 第一个 Tab：用户列表
            with gr.Tab("📋 用户列表"):
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

            # 第二个 Tab：用户输入详情
            with gr.Tab("🔍 用户输入详情"):
                gr.Markdown("## 用户输入图片和 Prompt 预览（按30天运行次数排序）")

                # 分页控制
                with gr.Row():
                    users_page_info = gr.Markdown("加载中...")
                    users_prev_btn = gr.Button("◀ 上一页", scale=1)
                    users_current_page = gr.Number(value=1, label="当前页", visible=False)
                    users_next_btn = gr.Button("下一页 ▶", scale=1)
                    refresh_btn = gr.Button("🔄 刷新", variant="primary", scale=1)

                # 用户列表展示区域
                users_gallery = gr.HTML(label="用户列表")

                # 展开用户详情区域
                gr.Markdown("---")
                gr.Markdown("### 📋 用户完整输入详情")
                with gr.Row():
                    detail_email = gr.Textbox(label="当前查看的用户邮箱", interactive=False, scale=3)
                    detail_page = gr.Number(value=1, label="详情页码", visible=False)
                    detail_prev_btn = gr.Button("◀ 上一页", scale=1)
                    detail_next_btn = gr.Button("下一页 ▶", scale=1)

                detail_page_info = gr.Markdown("")
                detail_gallery = gr.HTML(label="用户完整输入")

                # 渲染用户列表的函数
                def render_users_list(page):
                    page = int(page)
                    result = viewer.get_users_with_preview(page, 10)
                    users = result["users"]
                    total = result["total"]
                    total_pages = result["total_pages"]

                    if not users:
                        return "<p>未找到用户数据</p>", f"未找到数据", page

                    # 生成HTML
                    html = "<div style='max-width: 100%; padding: 10px;'>"

                    for user in users:
                        email = user["email"]
                        runs_30d = user["runs_30d"]
                        active_days_30d = user["active_days_30d"]
                        previews = user["previews"]

                        html += f"""
                        <div style='border: 2px solid #4a90d9; border-radius: 12px; padding: 20px; margin-bottom: 25px; background-color: #ffffff;'>
                            <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #eee;'>
                                <div>
                                    <span style='font-size: 18px; font-weight: bold; color: #333;'>📧 {email}</span>
                                </div>
                                <div style='display: flex; gap: 20px;'>
                                    <span style='background-color: #e3f2fd; padding: 5px 12px; border-radius: 15px; color: #1976d2; font-weight: bold;'>30天运行: {runs_30d}次</span>
                                    <span style='background-color: #e8f5e9; padding: 5px 12px; border-radius: 15px; color: #388e3c; font-weight: bold;'>活跃天数: {active_days_30d}天</span>
                                </div>
                            </div>
                            <div style='margin-top: 10px;'>
                                <strong style='color: #333;'>📝 最近输入预览:</strong>
                        """

                        if previews:
                            for i, preview in enumerate(previews):
                                html += f"""
                                <div style='background-color: #f8f9fa; padding: 12px; border-radius: 8px; margin-top: 10px; border-left: 4px solid #4a90d9;'>
                                    <div style='font-size: 12px; color: #666; margin-bottom: 8px;'>
                                        {preview['created_at']} | {preview['node_type']}
                                    </div>
                                """

                                if preview['input_text']:
                                    html += f"""
                                    <div style='color: #333; font-size: 14px; line-height: 1.5;'>{preview['input_text']}</div>
                                    """

                                if preview['has_image']:
                                    html += f"""
                                    <div style='margin-top: 8px;'>
                                        <img src='{preview['image_base64']}' style='max-width: 200px; max-height: 150px; border-radius: 4px; border: 1px solid #ddd;' />
                                    </div>
                                    """

                                html += "</div>"
                        else:
                            html += "<p style='color: #999; font-style: italic;'>暂无输入数据</p>"

                        html += f"""
                            </div>
                            <div style='margin-top: 15px; text-align: right;'>
                                <button onclick="document.querySelector('#detail_email_input textarea').value='{email}'; document.querySelector('#detail_email_input textarea').dispatchEvent(new Event('input', {{ bubbles: true }}));"
                                    style='background-color: #4a90d9; color: white; border: none; padding: 8px 20px; border-radius: 6px; cursor: pointer; font-size: 14px;'>
                                    👁️ 查看全部输入
                                </button>
                            </div>
                        </div>
                        """

                    html += "</div>"

                    page_info_text = f"第 {page}/{total_pages} 页 | 共 {total} 个用户"

                    return html, page_info_text, page

                # 渲染用户详情的函数
                def render_user_detail(email, page, page_size=20):
                    if not email:
                        return "", "请点击用户卡片的「查看全部输入」按钮", page

                    page = int(page)
                    result = viewer.get_user_inputs(email, page, page_size)
                    inputs = result["inputs"]
                    total = result["total"]
                    total_pages = result["total_pages"]

                    if not inputs:
                        return "<p style='color: #333;'>未找到该用户的输入数据</p>", f"未找到数据", page

                    # 生成HTML
                    html = "<div style='max-width: 100%; padding: 10px;'>"

                    for i, inp in enumerate(inputs):
                        html += f"""
                        <div style='border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin-bottom: 20px; background-color: #ffffff;'>
                            <div style='margin-bottom: 10px; color: #333;'>
                                <strong style='color: #333;'>#{i+1}</strong> |
                                <span style='color: #555;'>创建时间: {inp['created_at']}</span> |
                                <span style='color: #555;'>状态: {inp['status']}</span> |
                                <span style='color: #555;'>节点类型: {inp['node_type']}</span>
                            </div>
                        """

                        if inp['input_text']:
                            html += f"""
                            <div style='margin-bottom: 10px;'>
                                <strong style='color: #333;'>📝 Prompt:</strong>
                                <div style='background-color: #f8f9fa; padding: 12px; border-radius: 4px; margin-top: 5px; white-space: pre-wrap; color: #333; font-size: 14px; line-height: 1.6;'>{inp['input_text']}</div>
                            </div>
                            """

                        if inp['has_image']:
                            html += f"""
                            <div>
                                <strong style='color: #333;'>🖼️ 输入图片:</strong>
                                <div style='margin-top: 5px;'>
                                    <img src='{inp['image_base64']}' style='max-width: 100%; max-height: 400px; border-radius: 4px; border: 1px solid #ddd;' />
                                </div>
                            </div>
                            """

                        html += "</div>"

                    html += "</div>"

                    page_info_text = f"第 {page}/{total_pages} 页 | 共 {total} 条任务 | 当前显示 {len(inputs)} 条输入"

                    return html, page_info_text, page

                # 初始加载
                def init_load():
                    return render_users_list(1)

                # 用户列表分页
                def users_prev_page(page):
                    new_page = max(1, int(page) - 1)
                    return render_users_list(new_page)

                def users_next_page(page):
                    result = viewer.get_users_with_preview(int(page), 10)
                    total_pages = result["total_pages"]
                    new_page = min(total_pages, int(page) + 1) if total_pages > 0 else 1
                    return render_users_list(new_page)

                # 详情分页
                def detail_prev(email, page):
                    new_page = max(1, int(page) - 1)
                    return render_user_detail(email, new_page)

                def detail_next(email, page):
                    result = viewer.get_user_inputs(email, int(page), 20)
                    total_pages = result["total_pages"]
                    new_page = min(total_pages, int(page) + 1) if total_pages > 0 else 1
                    return render_user_detail(email, new_page)

                # 加载用户详情
                def load_user_detail(email):
                    html, info, page = render_user_detail(email, 1)
                    return email, html, info, page

                # 绑定事件
                demo.load(
                    fn=init_load,
                    outputs=[users_gallery, users_page_info, users_current_page]
                )

                refresh_btn.click(
                    fn=lambda page: render_users_list(page),
                    inputs=[users_current_page],
                    outputs=[users_gallery, users_page_info, users_current_page]
                )

                users_prev_btn.click(
                    fn=users_prev_page,
                    inputs=[users_current_page],
                    outputs=[users_gallery, users_page_info, users_current_page]
                )

                users_next_btn.click(
                    fn=users_next_page,
                    inputs=[users_current_page],
                    outputs=[users_gallery, users_page_info, users_current_page]
                )

                # 详情邮箱输入框（用于接收点击事件）
                detail_email_input = gr.Textbox(label="", visible=False, elem_id="detail_email_input")

                detail_email_input.change(
                    fn=load_user_detail,
                    inputs=[detail_email_input],
                    outputs=[detail_email, detail_gallery, detail_page_info, detail_page]
                )

                detail_prev_btn.click(
                    fn=detail_prev,
                    inputs=[detail_email, detail_page],
                    outputs=[detail_gallery, detail_page_info, detail_page]
                )

                detail_next_btn.click(
                    fn=detail_next,
                    inputs=[detail_email, detail_page],
                    outputs=[detail_gallery, detail_page_info, detail_page]
                )

    return demo


if __name__ == "__main__":
    demo = create_ui()
    demo.launch(
        server_name="0.0.0.0",  # 允许外部访问
        server_port=7860,
        share=False,  # 设为 True 可生成公网链接
    )
