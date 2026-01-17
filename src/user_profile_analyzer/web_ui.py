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
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import gradio as gr
import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi


# 配置日志
def setup_logging():
    """配置日志系统"""
    log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"web_ui_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()


def load_env():
    """加载环境变量"""
    app_env = os.environ.get("APP_ENV")
    if app_env:
        env_file = f".env.{app_env}"
    else:
        env_file = ".env.local"

    env_path = Path(__file__).resolve().parent.parent.parent / env_file
    load_dotenv(env_path)
    logger.info(f"加载环境配置文件: {env_file}")
    return env_file


class UserProfileViewer:
    """用户画像数据查看器"""

    def __init__(self):
        mongo_uri = os.getenv("MONGO_ATLAS_URI")
        mongo_db = os.getenv("MONGO_DB")

        if not mongo_uri or not mongo_db:
            raise ValueError("请确保环境变量中配置了 MONGO_ATLAS_URI 和 MONGO_DB")

        logger.info(f"连接MongoDB数据库: {mongo_db}")
        self.client = MongoClient(mongo_uri, server_api=ServerApi('1'))
        self.db = self.client[mongo_db]
        self.collection = self.db["user_workflow_profile"]
        logger.info("MongoDB连接成功")

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
        try:
            if not email:
                logger.warning("get_user_inputs: 未提供邮箱")
                return {"inputs": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

            logger.info(f"获取用户输入详情 - 邮箱: {email}, 页码: {page}")

            # 获取用户ID
            user_doc = self.collection.find_one(
                {"user_email": email},
                {"user_id": 1}
            )

            if not user_doc:
                logger.warning(f"未找到用户: {email}")
                return {"inputs": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

            user_id = user_doc.get("user_id")

            # 从 flow_task 集合获取用户的所有任务
            flow_task_collection = self.db["flow_task"]

            # 计算总数
            total_tasks = flow_task_collection.count_documents({"user_id": user_id})
            total_pages = (total_tasks + page_size - 1) // page_size if total_tasks > 0 else 1

            # 边界检查
            if page < 1:
                page = 1
            if page > total_pages:
                page = total_pages

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

            logger.info(f"成功获取用户 {email} 的 {len(inputs)} 条输入数据")

            return {
                "inputs": inputs,
                "total": total_tasks,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
        except Exception as e:
            logger.error(f"获取用户输入详情失败 - 邮箱: {email}, 错误: {str(e)}", exc_info=True)
            return {"inputs": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

    def get_users_with_preview(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取用户列表和输入预览（按30天运行次数排序）

        Args:
            page: 页码（从1开始）
            page_size: 每页用户数量

        Returns:
            包含用户列表和分页信息的字典
        """
        try:
            logger.info(f"获取用户列表预览 - 页码: {page}, 每页: {page_size}")

            # 计算总数
            total_users = self.collection.count_documents({})
            total_pages = (total_users + page_size - 1) // page_size if total_users > 0 else 1

            # 边界检查
            if page < 1:
                page = 1
            if page > total_pages:
                page = total_pages

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

            logger.info(f"成功获取 {len(users)} 个用户数据")

            return {
                "users": users,
                "total": total_users,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
        except Exception as e:
            logger.error(f"获取用户列表预览失败: {str(e)}", exc_info=True)
            return {
                "users": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0
            }


def create_ui():
    """创建 Gradio UI"""
    env_file = load_env()
    print(f"使用配置文件: {env_file}")

    viewer = UserProfileViewer()
    stats = viewer.get_stats()

    # JavaScript代码 - 通过head参数注入，确保执行
    custom_head = """
    <style>
        /* 如果URL有email参数，初始隐藏页面内容 */
        .gradio-container.loading-user-detail {
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        .gradio-container.loaded {
            opacity: 1;
        }
    </style>
    <script>
        // 检测URL参数并自动切换到单用户详情Tab
        function checkURLForSingleUser() {
            const urlParams = new URLSearchParams(window.location.search);
            const email = urlParams.get('email');

            if (email) {
                console.log('✅ 检测到email参数:', email);

                // 立即隐藏页面内容，避免用户看到切换过程
                const container = document.querySelector('.gradio-container');
                if (container) {
                    container.classList.add('loading-user-detail');
                }

                // 等待Gradio完全加载
                setTimeout(function() {
                    console.log('🔄 开始尝试切换Tab...');

                    // 查找Tab
                    let tabs = document.querySelectorAll('button[role="tab"]');
                    console.log('📋 找到Tab数量:', tabs.length);

                    // 查找"单用户详情"Tab
                    let targetTab = null;
                    tabs.forEach((tab, index) => {
                        if (tab.textContent.includes('单用户详情')) {
                            targetTab = tab;
                            console.log('✅ 找到目标Tab - 索引' + index);
                        }
                    });

                    // 点击Tab
                    if (targetTab) {
                        targetTab.click();
                        console.log('✅ 已点击「单用户详情」Tab');
                    }

                    // 等待Tab切换完成后填充数据
                    setTimeout(function() {
                        const emailInput = document.querySelector('#single_user_email textarea');
                        const loadBtn = document.querySelector('#single_user_load_btn');

                        if (emailInput && loadBtn) {
                            emailInput.value = decodeURIComponent(email);
                            emailInput.dispatchEvent(new Event('input', {bubbles: true}));
                            console.log('✅ 已填充邮箱:', emailInput.value);

                            setTimeout(function() {
                                loadBtn.click();
                                console.log('✅ 已点击加载按钮');

                                // 显示页面内容
                                setTimeout(function() {
                                    const container = document.querySelector('.gradio-container');
                                    if (container) {
                                        container.classList.remove('loading-user-detail');
                                        container.classList.add('loaded');
                                    }
                                    console.log('✅ 页面显示完成');
                                }, 500);
                            }, 300);
                        }

                        // 修改页面标题
                        document.title = decodeURIComponent(email) + ' - 用户详情';
                    }, 500);
                }, 1500);
            }
        }

        // 页面加载完成后执行
        window.addEventListener('load', function() {
            console.log('🚀 页面加载完成，开始检测URL参数...');
            checkURLForSingleUser();
        });
    </script>
    """

    with gr.Blocks(title="用户画像分析系统") as demo:
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

                # 添加自动检测URL参数的JavaScript
                gr.HTML("""
                <script>
                    // 检测URL参数并自动加载用户详情
                    function checkURLParams() {
                        const urlParams = new URLSearchParams(window.location.search);
                        const email = urlParams.get('email');

                        if (email) {
                            // 等待页面完全加载
                            setTimeout(function() {
                                // 1. 自动切换到"用户输入详情" Tab
                                const tabs = document.querySelectorAll('.tab-nav button');
                                tabs.forEach(tab => {
                                    if (tab.textContent.includes('用户输入详情')) {
                                        tab.click();
                                    }
                                });

                                // 2. 等待Tab切换完成后，隐藏用户列表区域
                                setTimeout(function() {
                                    const gallery = document.querySelector("#users_gallery");
                                    if (gallery) {
                                        // 找到用户列表所在的所有行并隐藏
                                        const parentContainer = gallery.closest('.tabitem');
                                        if (parentContainer) {
                                            const rows = parentContainer.querySelectorAll('.gr-row');
                                            rows.forEach((row, index) => {
                                                // 隐藏前面的分页控制和用户列表，但保留详情区域
                                                if (index < 3) {  // 前3行是分页控制和用户列表
                                                    row.style.display = 'none';
                                                }
                                            });
                                        }
                                    }

                                    // 3. 自动填充邮箱并加载详情
                                    const emailInput = document.querySelector("#detail_email_input textarea");
                                    const loadBtn = document.querySelector("#load_detail_btn");

                                    if (emailInput && loadBtn) {
                                        emailInput.value = decodeURIComponent(email);
                                        emailInput.dispatchEvent(new Event("input", {bubbles: true}));

                                        setTimeout(function() {
                                            loadBtn.click();
                                        }, 300);
                                    }

                                    // 4. 修改页面标题
                                    document.title = decodeURIComponent(email) + " - 用户详情";
                                }, 500);
                            }, 800);
                        }
                    }

                    // 页面加载时执行
                    if (document.readyState === 'loading') {
                        document.addEventListener('DOMContentLoaded', checkURLParams);
                    } else {
                        checkURLParams();
                    }
                </script>
                """)

                # 分页控制（优化版）
                with gr.Row():
                    users_first_btn = gr.Button("⏮ 首页", scale=1)
                    users_prev_btn = gr.Button("◀ 上一页", scale=1)
                    users_page_info = gr.HTML("""
                        <div style='text-align: center; padding: 15px;'>
                            <div style='display: inline-block; width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid #667eea; border-radius: 50%; animation: spin 1s linear infinite;'></div>
                            <p style='margin-top: 15px; color: #667eea; font-size: 16px; font-weight: 500;'>⏳ 正在加载用户数据...</p>
                        </div>
                        <style>
                            @keyframes spin {
                                0% { transform: rotate(0deg); }
                                100% { transform: rotate(360deg); }
                            }
                        </style>
                    """)
                    users_page_input = gr.Number(value=1, label="跳转到第", minimum=1, scale=1)
                    users_jump_btn = gr.Button("跳转", variant="secondary", scale=1)
                    users_next_btn = gr.Button("下一页 ▶", scale=1)
                    users_last_btn = gr.Button("末页 ⏭", scale=1)

                with gr.Row():
                    users_page_size = gr.Dropdown(
                        choices=[10, 20, 30, 50],
                        value=20,
                        label="每页显示",
                        scale=1
                    )
                    refresh_btn = gr.Button("🔄 刷新", variant="primary", scale=1)
                    users_current_page = gr.Number(value=1, label="当前页", visible=False)

                # 用户列表展示区域
                users_gallery = gr.HTML(label="用户列表", elem_id="users_gallery")

                # 展开用户详情区域
                gr.Markdown("---")
                gr.Markdown("### 📋 用户完整输入详情")

                # 添加一个简单的邮箱输入框让用户手动输入或点击按钮自动填充
                with gr.Row():
                    detail_email_input = gr.Textbox(
                        label="手动输入邮箱查看该用户的所有输入",
                        placeholder="输入邮箱，例如: user@example.com",
                        scale=3,
                        elem_id="detail_email_input"
                    )
                    load_detail_btn = gr.Button("🔍 加载详情", variant="primary", scale=1, elem_id="load_detail_btn")

                # 分页按钮行 - 初始隐藏，加载用户后显示
                detail_pagination_row = gr.Row(visible=False)
                with detail_pagination_row:
                    detail_first_btn = gr.Button("⏮ 首页", scale=1)
                    detail_prev_btn = gr.Button("◀ 上一页", scale=1)
                    detail_page_info = gr.HTML("<div style='text-align: center; padding: 10px;'></div>")
                    detail_page_input = gr.Number(value=1, label="跳转到第", minimum=1, scale=1)
                    detail_jump_btn = gr.Button("跳转", variant="secondary", scale=1)
                    detail_next_btn = gr.Button("下一页 ▶", scale=1)
                    detail_last_btn = gr.Button("末页 ⏭", scale=1)

                with gr.Row():
                    detail_email = gr.Textbox(label="当前查看的用户", interactive=False, scale=3, visible=False)
                    detail_page = gr.Number(value=1, label="详情页码", visible=False)

                detail_gallery = gr.HTML(label="用户完整输入", elem_id="detail_gallery")

                # 渲染用户列表的函数（支持可变页面大小）
                def render_users_list(page, page_size=20):
                    try:
                        page = int(page)
                        page_size = int(page_size)
                        logger.info(f"渲染用户列表 - 页码: {page}, 每页: {page_size}")
                        result = viewer.get_users_with_preview(page, page_size)
                        users = result["users"]
                        total = result["total"]
                        total_pages = result["total_pages"]

                        if not users:
                            logger.warning("未找到用户数据")
                            return "<p>未找到用户数据</p>", f"未找到数据", page

                        # 生成HTML（加载动画CSS）
                        html = """
                        <style>
                            @keyframes spin {
                                0% { transform: rotate(0deg); }
                                100% { transform: rotate(360deg); }
                            }
                            .loading-spinner {
                                display: inline-block;
                                width: 20px;
                                height: 20px;
                                border: 3px solid #f3f3f3;
                                border-top: 3px solid #4a90d9;
                                border-radius: 50%;
                                animation: spin 1s linear infinite;
                            }
                        </style>
                        <div style='max-width: 100%; padding: 10px;'>
                        """

                        # 优化的分页信息
                        html += f"""
                        <div style='display: flex; justify-content: space-between; padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; margin-bottom: 20px; color: white;'>
                            <span style='font-size: 16px;'>📊 共 <strong>{total}</strong> 个用户</span>
                            <span style='font-size: 16px;'>📄 第 <strong>{page}</strong>/<strong>{total_pages}</strong> 页</span>
                            <span style='font-size: 16px;'>👁️ 每页显示 <strong>{page_size}</strong> 个</span>
                        </div>
                        """

                        for user in users:
                            email = user["email"]
                            # 转义单引号和双引号，避免JavaScript注入
                            safe_email = email.replace("'", "\\'").replace('"', '\\"')
                            runs_30d = user["runs_30d"]
                            active_days_30d = user["active_days_30d"]
                            previews = user["previews"]

                            html += f"""
                            <div style='border: 2px solid #4a90d9; border-radius: 12px; padding: 20px; margin-bottom: 25px; background-color: #ffffff; box-shadow: 0 2px 8px rgba(0,0,0,0.1); transition: all 0.3s;' onmouseover='this.style.boxShadow="0 4px 16px rgba(74,144,217,0.3)"' onmouseout='this.style.boxShadow="0 2px 8px rgba(0,0,0,0.1)"'>
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

                            # 新窗口打开详情按钮
                            html += f"""
                                </div>
                                <div style='margin-top: 15px; text-align: center;'>
                                    <button onclick='
                                        window.open("?email={safe_email}", "_blank");
                                    ' style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 12px 30px; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: bold; width: 100%; transition: all 0.3s; box-shadow: 0 2px 8px rgba(102,126,234,0.3);'
                                    onmouseover='this.style.transform="translateY(-2px)"; this.style.boxShadow="0 4px 12px rgba(102,126,234,0.5)";'
                                    onmouseout='this.style.transform="translateY(0)"; this.style.boxShadow="0 2px 8px rgba(102,126,234,0.3)";'>
                                        📋 查看该用户所有输入
                                    </button>
                                </div>
                            </div>
                            """

                        html += "</div>"

                        page_info_text = f"""
                        <div style='text-align: center; font-size: 16px; color: #333;'>
                            📄 第 <strong style='color: #667eea;'>{page}</strong>/<strong style='color: #764ba2;'>{total_pages}</strong> 页 |
                            📊 共 <strong style='color: #667eea;'>{total}</strong> 个用户 |
                            👁️ 当前显示 <strong style='color: #764ba2;'>{len(users)}</strong> 个
                        </div>
                        """

                        logger.info(f"成功渲染 {len(users)} 个用户卡片")
                        return html, page_info_text, page
                    except Exception as e:
                        logger.error(f"渲染用户列表失败: {str(e)}", exc_info=True)
                        return f"<p style='color: red;'>加载失败: {str(e)}</p>", "加载失败", 1

                # 渲染用户详情的函数
                def render_user_detail(email, page, page_size=20):
                    try:
                        if not email:
                            return "", "请点击用户卡片的「查看全部输入」按钮", page

                        page = int(page)
                        logger.info(f"渲染用户详情 - 邮箱: {email}, 页码: {page}")
                        result = viewer.get_user_inputs(email, page, page_size)
                        inputs = result["inputs"]
                        total = result["total"]
                        total_pages = result["total_pages"]

                        if not inputs:
                            logger.warning(f"未找到用户 {email} 的输入数据")
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

                        page_info_text = f"""
                        <div style='text-align: center; font-size: 16px; color: #333;'>
                            📄 第 <strong style='color: #667eea;'>{page}</strong>/<strong style='color: #764ba2;'>{total_pages}</strong> 页 |
                            📊 共 <strong style='color: #667eea;'>{total}</strong> 条任务 |
                            👁️ 当前显示 <strong style='color: #764ba2;'>{len(inputs)}</strong> 条输入
                        </div>
                        """

                        logger.info(f"成功渲染用户 {email} 的 {len(inputs)} 条输入")
                        return html, page_info_text, page
                    except Exception as e:
                        logger.error(f"渲染用户详情失败 - 邮箱: {email}, 错误: {str(e)}", exc_info=True)
                        return f"<p style='color: red;'>加载失败: {str(e)}</p>", "加载失败", 1

                # 初始加载
                def init_load(page_size):
                    return render_users_list(1, page_size)

                # 用户列表分页函数（全部支持page_size参数）
                def users_first_page(page_size):
                    try:
                        logger.info("用户列表跳转首页")
                        return render_users_list(1, page_size)
                    except Exception as e:
                        logger.error(f"用户列表跳转首页失败: {str(e)}", exc_info=True)
                        return f"<p style='color: red;'>加载失败: {str(e)}</p>", "加载失败", 1

                def users_prev_page(page, page_size):
                    try:
                        new_page = max(1, int(page) - 1)
                        logger.info(f"用户列表上一页: {page} -> {new_page}")
                        return render_users_list(new_page, page_size)
                    except Exception as e:
                        logger.error(f"用户列表上一页失败: {str(e)}", exc_info=True)
                        return f"<p style='color: red;'>加载失败: {str(e)}</p>", "加载失败", 1

                def users_next_page(page, page_size):
                    try:
                        result = viewer.get_users_with_preview(int(page), int(page_size))
                        total_pages = result["total_pages"]
                        new_page = min(total_pages, int(page) + 1) if total_pages > 0 else 1
                        logger.info(f"用户列表下一页: {page} -> {new_page}")
                        return render_users_list(new_page, page_size)
                    except Exception as e:
                        logger.error(f"用户列表下一页失败: {str(e)}", exc_info=True)
                        return f"<p style='color: red;'>加载失败: {str(e)}</p>", "加载失败", 1

                def users_last_page(page_size):
                    try:
                        result = viewer.get_users_with_preview(1, int(page_size))
                        total_pages = result["total_pages"]
                        logger.info(f"用户列表跳转末页: {total_pages}")
                        return render_users_list(total_pages, page_size)
                    except Exception as e:
                        logger.error(f"用户列表跳转末页失败: {str(e)}", exc_info=True)
                        return f"<p style='color: red;'>加载失败: {str(e)}</p>", "加载失败", 1

                def users_jump_to_page(target_page, page_size):
                    try:
                        target_page = int(target_page)
                        result = viewer.get_users_with_preview(1, int(page_size))
                        total_pages = result["total_pages"]

                        # 边界检查
                        if target_page < 1:
                            target_page = 1
                        elif target_page > total_pages:
                            target_page = total_pages

                        logger.info(f"用户列表跳转到页: {target_page}")
                        return render_users_list(target_page, page_size)
                    except Exception as e:
                        logger.error(f"用户列表跳转失败: {str(e)}", exc_info=True)
                        return f"<p style='color: red;'>加载失败: {str(e)}</p>", "加载失败", 1

                # 详情分页函数
                def detail_first_page(email):
                    try:
                        logger.info(f"详情跳转首页: 邮箱={email}")
                        return render_user_detail(email, 1)
                    except Exception as e:
                        logger.error(f"详情跳转首页失败: {str(e)}", exc_info=True)
                        return f"<p style='color: red;'>加载失败: {str(e)}</p>", "加载失败", 1

                def detail_prev(email, page):
                    try:
                        new_page = max(1, int(page) - 1)
                        logger.info(f"详情上一页: 邮箱={email}, {page} -> {new_page}")
                        return render_user_detail(email, new_page)
                    except Exception as e:
                        logger.error(f"详情上一页失败: {str(e)}", exc_info=True)
                        return f"<p style='color: red;'>加载失败: {str(e)}</p>", "加载失败", 1

                def detail_next(email, page):
                    try:
                        result = viewer.get_user_inputs(email, int(page), 20)
                        total_pages = result["total_pages"]
                        new_page = min(total_pages, int(page) + 1) if total_pages > 0 else 1
                        logger.info(f"详情下一页: 邮箱={email}, {page} -> {new_page}")
                        return render_user_detail(email, new_page)
                    except Exception as e:
                        logger.error(f"详情下一页失败: {str(e)}", exc_info=True)
                        return f"<p style='color: red;'>加载失败: {str(e)}</p>", "加载失败", 1

                def detail_last_page(email):
                    try:
                        result = viewer.get_user_inputs(email, 1, 20)
                        total_pages = result["total_pages"]
                        logger.info(f"详情跳转末页: 邮箱={email}, 页码={total_pages}")
                        return render_user_detail(email, total_pages)
                    except Exception as e:
                        logger.error(f"详情跳转末页失败: {str(e)}", exc_info=True)
                        return f"<p style='color: red;'>加载失败: {str(e)}</p>", "加载失败", 1

                def detail_jump_to_page(email, target_page):
                    try:
                        target_page = int(target_page)
                        result = viewer.get_user_inputs(email, 1, 20)
                        total_pages = result["total_pages"]

                        # 边界检查
                        if target_page < 1:
                            target_page = 1
                        elif target_page > total_pages:
                            target_page = total_pages

                        logger.info(f"详情跳转到页: 邮箱={email}, 页码={target_page}")
                        return render_user_detail(email, target_page)
                    except Exception as e:
                        logger.error(f"详情跳转失败: {str(e)}", exc_info=True)
                        return f"<p style='color: red;'>加载失败: {str(e)}</p>", "加载失败", 1

                # 加载用户详情
                def load_user_detail(email):
                    try:
                        logger.info(f"加载用户详情: {email}")
                        html, info, page = render_user_detail(email, 1)
                        # 如果有邮箱，显示分页按钮行
                        show_pagination = gr.update(visible=bool(email and email.strip()))
                        return email, html, info, page, show_pagination
                    except Exception as e:
                        logger.error(f"加载用户详情失败: {str(e)}", exc_info=True)
                        return email, f"<p style='color: red;'>加载失败: {str(e)}</p>", "加载失败", 1, gr.update(visible=False)

                # 绑定事件 - 用户列表区域
                demo.load(
                    fn=init_load,
                    inputs=[users_page_size],
                    outputs=[users_gallery, users_page_info, users_current_page]
                )

                # 首页按钮
                users_first_btn.click(
                    fn=users_first_page,
                    inputs=[users_page_size],
                    outputs=[users_gallery, users_page_info, users_current_page]
                )

                # 上一页按钮
                users_prev_btn.click(
                    fn=users_prev_page,
                    inputs=[users_current_page, users_page_size],
                    outputs=[users_gallery, users_page_info, users_current_page]
                )

                # 下一页按钮
                users_next_btn.click(
                    fn=users_next_page,
                    inputs=[users_current_page, users_page_size],
                    outputs=[users_gallery, users_page_info, users_current_page]
                )

                # 末页按钮
                users_last_btn.click(
                    fn=users_last_page,
                    inputs=[users_page_size],
                    outputs=[users_gallery, users_page_info, users_current_page]
                )

                # 跳转按钮
                users_jump_btn.click(
                    fn=users_jump_to_page,
                    inputs=[users_page_input, users_page_size],
                    outputs=[users_gallery, users_page_info, users_current_page]
                )

                # 页码输入框回车
                users_page_input.submit(
                    fn=users_jump_to_page,
                    inputs=[users_page_input, users_page_size],
                    outputs=[users_gallery, users_page_info, users_current_page]
                )

                # 刷新按钮
                refresh_btn.click(
                    fn=lambda page, page_size: render_users_list(page, page_size),
                    inputs=[users_current_page, users_page_size],
                    outputs=[users_gallery, users_page_info, users_current_page]
                )

                # 页面大小改变时重新加载
                users_page_size.change(
                    fn=lambda page_size: render_users_list(1, page_size),
                    inputs=[users_page_size],
                    outputs=[users_gallery, users_page_info, users_current_page]
                )

                # 绑定事件 - 用户详情区域
                # 加载详情按钮
                load_detail_btn.click(
                    fn=load_user_detail,
                    inputs=[detail_email_input],
                    outputs=[detail_email, detail_gallery, detail_page_info, detail_page, detail_pagination_row]
                )

                # 邮箱输入框回车
                detail_email_input.submit(
                    fn=load_user_detail,
                    inputs=[detail_email_input],
                    outputs=[detail_email, detail_gallery, detail_page_info, detail_page, detail_pagination_row]
                )

                # 详情首页按钮
                detail_first_btn.click(
                    fn=detail_first_page,
                    inputs=[detail_email],
                    outputs=[detail_gallery, detail_page_info, detail_page]
                )

                # 详情上一页按钮
                detail_prev_btn.click(
                    fn=detail_prev,
                    inputs=[detail_email, detail_page],
                    outputs=[detail_gallery, detail_page_info, detail_page]
                )

                # 详情下一页按钮
                detail_next_btn.click(
                    fn=detail_next,
                    inputs=[detail_email, detail_page],
                    outputs=[detail_gallery, detail_page_info, detail_page]
                )

                # 详情末页按钮
                detail_last_btn.click(
                    fn=detail_last_page,
                    inputs=[detail_email],
                    outputs=[detail_gallery, detail_page_info, detail_page]
                )

                # 详情跳转按钮
                detail_jump_btn.click(
                    fn=detail_jump_to_page,
                    inputs=[detail_email, detail_page_input],
                    outputs=[detail_gallery, detail_page_info, detail_page]
                )

                # 详情页码输入框回车
                detail_page_input.submit(
                    fn=detail_jump_to_page,
                    inputs=[detail_email, detail_page_input],
                    outputs=[detail_gallery, detail_page_info, detail_page]
                )

            # 第三个 Tab：单用户详情（简洁美观版）
            with gr.Tab("📋 单用户详情", elem_id="single_user_detail_tab"):
                # 简洁美观的头部
                gr.HTML("""
                <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(102,126,234,0.3);'>
                    <h2 style='color: white; margin: 0; font-size: 28px; font-weight: 600;'>👤 用户详细输入记录</h2>
                    <p style='color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 14px;'>查看用户的所有输入图片和Prompt</p>
                </div>
                """)

                # 邮箱输入区域
                with gr.Row():
                    single_user_email = gr.Textbox(
                        label="",
                        placeholder="输入用户邮箱，例如: user@example.com",
                        scale=4,
                        elem_id="single_user_email",
                        show_label=False
                    )
                    single_user_load_btn = gr.Button(
                        "🔍 加载用户数据",
                        variant="primary",
                        scale=1,
                        elem_id="single_user_load_btn",
                        size="lg"
                    )

                # 用户信息显示区（加载后显示）
                single_user_info = gr.HTML("")

                # 分页控制
                with gr.Row():
                    single_detail_first_btn = gr.Button("⏮ 首页", scale=1)
                    single_detail_prev_btn = gr.Button("◀ 上一页", scale=1)
                    single_detail_page_info = gr.HTML("<div style='text-align: center; padding: 10px;'></div>")
                    single_detail_page_input = gr.Number(value=1, label="跳转到", minimum=1, scale=1)
                    single_detail_jump_btn = gr.Button("跳转", variant="secondary", scale=1)
                    single_detail_next_btn = gr.Button("下一页 ▶", scale=1)
                    single_detail_last_btn = gr.Button("末页 ⏭", scale=1)

                # 隐藏的状态变量
                single_detail_current_email = gr.Textbox(value="", visible=False)
                single_detail_current_page = gr.Number(value=1, visible=False)

                # 详情内容展示区
                single_detail_content = gr.HTML(label="", elem_id="single_detail_content")

                # 渲染单用户详情的函数
                def render_single_user_detail(email, page=1):
                    try:
                        if not email:
                            return "", "", "<div style='text-align: center; padding: 50px; color: #999;'>请输入用户邮箱</div>", email, page

                        page = int(page)
                        logger.info(f"渲染单用户详情 - 邮箱: {email}, 页码: {page}")

                        # 获取用户基本信息
                        user_doc = viewer.collection.find_one(
                            {"user_email": email},
                            {"user_id": 1, "user_email": 1, "stats": 1}
                        )

                        if not user_doc:
                            return "", "", f"<div style='text-align: center; padding: 50px; color: #ff6b6b;'>❌ 未找到用户: {email}</div>", email, page

                        # 用户信息卡片
                        stats = user_doc.get("stats", {})
                        info_html = f"""
                        <div style='background: white; border-radius: 12px; padding: 25px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                            <div style='display: flex; align-items: center; gap: 15px; margin-bottom: 20px;'>
                                <div style='width: 60px; height: 60px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center;'>
                                    <span style='font-size: 30px;'>👤</span>
                                </div>
                                <div>
                                    <h3 style='margin: 0; font-size: 20px; color: #333;'>{email}</h3>
                                    <p style='margin: 5px 0 0 0; color: #666; font-size: 14px;'>用户详细输入记录</p>
                                </div>
                            </div>
                            <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;'>
                                <div style='background: #e3f2fd; padding: 15px; border-radius: 8px;'>
                                    <div style='color: #1976d2; font-size: 12px; margin-bottom: 5px;'>30天运行次数</div>
                                    <div style='color: #1565c0; font-size: 24px; font-weight: bold;'>{stats.get('total_runs_30d', 0)}</div>
                                </div>
                                <div style='background: #e8f5e9; padding: 15px; border-radius: 8px;'>
                                    <div style='color: #388e3c; font-size: 12px; margin-bottom: 5px;'>30天活跃天数</div>
                                    <div style='color: #2e7d32; font-size: 24px; font-weight: bold;'>{stats.get('active_days_30d', 0)}</div>
                                </div>
                            </div>
                        </div>
                        """

                        # 获取用户输入数据
                        result = viewer.get_user_inputs(email, page, 20)
                        inputs = result["inputs"]
                        total = result["total"]
                        total_pages = result["total_pages"]

                        if not inputs:
                            content_html = "<div style='text-align: center; padding: 50px; color: #999;'>该用户暂无输入数据</div>"
                        else:
                            content_html = "<div style='display: grid; gap: 20px;'>"

                            for i, inp in enumerate(inputs):
                                content_html += f"""
                                <div style='background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); transition: all 0.3s;'
                                     onmouseover='this.style.boxShadow="0 4px 16px rgba(0,0,0,0.15)"'
                                     onmouseout='this.style.boxShadow="0 2px 8px rgba(0,0,0,0.1)"'>
                                    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0;'>
                                        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 6px 12px; border-radius: 20px; font-size: 14px; font-weight: 600;'>
                                            #{(page-1)*20 + i + 1}
                                        </div>
                                        <div style='color: #666; font-size: 13px;'>
                                            <span style='margin-right: 15px;'>📅 {inp['created_at']}</span>
                                            <span style='margin-right: 15px;'>📊 {inp['status']}</span>
                                            <span>🔧 {inp['node_type']}</span>
                                        </div>
                                    </div>
                                """

                                if inp['input_text']:
                                    content_html += f"""
                                    <div style='margin-bottom: 15px;'>
                                        <div style='color: #667eea; font-weight: 600; margin-bottom: 8px; font-size: 14px;'>📝 Prompt:</div>
                                        <div style='background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #667eea; white-space: pre-wrap; color: #333; font-size: 14px; line-height: 1.8;'>{inp['input_text']}</div>
                                    </div>
                                    """

                                if inp['has_image']:
                                    content_html += f"""
                                    <div>
                                        <div style='color: #764ba2; font-weight: 600; margin-bottom: 8px; font-size: 14px;'>🖼️ 输入图片:</div>
                                        <div style='text-align: center; background: #f8f9fa; padding: 15px; border-radius: 8px;'>
                                            <img src='{inp['image_base64']}' style='max-width: 100%; max-height: 500px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);' />
                                        </div>
                                    </div>
                                    """

                                content_html += "</div>"

                            content_html += "</div>"

                        # 分页信息
                        page_info_html = f"""
                        <div style='text-align: center; padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; color: white; font-size: 16px;'>
                            📄 第 <strong>{page}</strong>/<strong>{total_pages}</strong> 页 |
                            📊 共 <strong>{total}</strong> 条任务 |
                            👁️ 当前显示 <strong>{len(inputs)}</strong> 条
                        </div>
                        """

                        logger.info(f"成功渲染单用户详情 - 邮箱: {email}, 数据条数: {len(inputs)}")
                        return info_html, page_info_html, content_html, email, page

                    except Exception as e:
                        logger.error(f"渲染单用户详情失败 - 邮箱: {email}, 错误: {str(e)}", exc_info=True)
                        return "", "", f"<div style='text-align: center; padding: 50px; color: #ff6b6b;'>❌ 加载失败: {str(e)}</div>", email, 1

                # 加载按钮点击
                def load_single_user(email):
                    return render_single_user_detail(email, 1)

                # 分页函数
                def single_first_page(email):
                    return render_single_user_detail(email, 1)

                def single_prev_page(email, page):
                    new_page = max(1, int(page) - 1)
                    return render_single_user_detail(email, new_page)

                def single_next_page(email, page):
                    result = viewer.get_user_inputs(email, int(page), 20)
                    total_pages = result["total_pages"]
                    new_page = min(total_pages, int(page) + 1) if total_pages > 0 else 1
                    return render_single_user_detail(email, new_page)

                def single_last_page(email):
                    result = viewer.get_user_inputs(email, 1, 20)
                    total_pages = result["total_pages"]
                    return render_single_user_detail(email, total_pages if total_pages > 0 else 1)

                def single_jump_to_page(email, target_page):
                    target_page = int(target_page)
                    result = viewer.get_user_inputs(email, 1, 20)
                    total_pages = result["total_pages"]
                    if target_page < 1:
                        target_page = 1
                    elif target_page > total_pages:
                        target_page = total_pages
                    return render_single_user_detail(email, target_page)

                # 绑定事件
                single_user_load_btn.click(
                    fn=load_single_user,
                    inputs=[single_user_email],
                    outputs=[single_user_info, single_detail_page_info, single_detail_content, single_detail_current_email, single_detail_current_page]
                )

                single_user_email.submit(
                    fn=load_single_user,
                    inputs=[single_user_email],
                    outputs=[single_user_info, single_detail_page_info, single_detail_content, single_detail_current_email, single_detail_current_page]
                )

                single_detail_first_btn.click(
                    fn=single_first_page,
                    inputs=[single_detail_current_email],
                    outputs=[single_user_info, single_detail_page_info, single_detail_content, single_detail_current_email, single_detail_current_page]
                )

                single_detail_prev_btn.click(
                    fn=single_prev_page,
                    inputs=[single_detail_current_email, single_detail_current_page],
                    outputs=[single_user_info, single_detail_page_info, single_detail_content, single_detail_current_email, single_detail_current_page]
                )

                single_detail_next_btn.click(
                    fn=single_next_page,
                    inputs=[single_detail_current_email, single_detail_current_page],
                    outputs=[single_user_info, single_detail_page_info, single_detail_content, single_detail_current_email, single_detail_current_page]
                )

                single_detail_last_btn.click(
                    fn=single_last_page,
                    inputs=[single_detail_current_email],
                    outputs=[single_user_info, single_detail_page_info, single_detail_content, single_detail_current_email, single_detail_current_page]
                )

                single_detail_jump_btn.click(
                    fn=single_jump_to_page,
                    inputs=[single_detail_current_email, single_detail_page_input],
                    outputs=[single_user_info, single_detail_page_info, single_detail_content, single_detail_current_email, single_detail_current_page]
                )

                single_detail_page_input.submit(
                    fn=single_jump_to_page,
                    inputs=[single_detail_current_email, single_detail_page_input],
                    outputs=[single_user_info, single_detail_page_info, single_detail_content, single_detail_current_email, single_detail_current_page]
                )

    return demo, custom_head


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("启动用户画像分析系统 Web UI")
    logger.info("=" * 60)

    try:
        demo, custom_head = create_ui()
        logger.info("Gradio UI 创建成功")
        logger.info("启动服务器 - 地址: 0.0.0.0:7860")

        demo.launch(
            server_name="0.0.0.0",  # 允许外部访问
            server_port=7860,
            share=False,  # 设为 True 可生成公网链接
            head=custom_head,
        )
    except Exception as e:
        logger.error(f"启动失败: {str(e)}", exc_info=True)
        raise
