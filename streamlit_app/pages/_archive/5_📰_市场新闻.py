import streamlit as st
import sys
import os
from datetime import datetime

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import EquilibraAPIClient

st.set_page_config(page_title="市场新闻", page_icon="📰", layout="wide")

# 初始化 API 客户端
@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return EquilibraAPIClient(base_url=api_url)

api_client = get_api_client()

st.title("📰 市场新闻")
st.markdown("基于 pgvector 的智能新闻管理与语义搜索")
st.markdown("---")

# 标签页
tab1, tab2 = st.tabs(["📋 新闻列表", "➕ 添加新闻"])

with tab1:
    st.markdown("### 📋 最新市场新闻")

    # 刷新按钮
    col1, col2 = st.columns([5, 1])
    with col2:
        if st.button("🔄 刷新", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # 获取新闻列表
    @st.cache_data(ttl=60)
    def load_news(limit=10):
        return api_client.get_latest_news(limit=limit)

    try:
        news_data = load_news(limit=20)
        news_list = news_data.get("news", [])

        if news_list:
            st.info(f"共 {news_data.get('count', 0)} 条新闻")

            # 显示新闻列表
            for news in news_list:
                with st.expander(f"**{news['title']}** - {news.get('source', '未知来源')}"):
                    col1, col2 = st.columns([4, 1])

                    with col1:
                        st.markdown(news['content'])

                    with col2:
                        if news.get('published_at'):
                            st.markdown(f"**发布时间**")
                            st.markdown(f"{news['published_at']}")

                        if news.get('created_at'):
                            st.markdown(f"**收录时间**")
                            st.markdown(f"{news['created_at']}")

                        st.markdown(f"**ID**: {news['id']}")

        else:
            st.warning("暂无新闻数据")
            st.info("💡 提示：您可以在「添加新闻」标签页中添加市场新闻")

    except Exception as e:
        st.error(f"❌ 无法加载新闻: {str(e)}")

with tab2:
    st.markdown("### ➕ 添加市场新闻")
    st.info("添加的新闻将自动生成 Embedding，用于 AI 分析时的语义检索")

    with st.form("add_news_form"):
        news_title = st.text_input(
            "新闻标题 *",
            placeholder="例如：比特币突破 10 万美元"
        )

        news_content = st.text_area(
            "新闻内容 *",
            placeholder="输入新闻正文...",
            height=200
        )

        col1, col2 = st.columns(2)

        with col1:
            news_source = st.text_input(
                "新闻来源",
                placeholder="例如：财经新闻、彭博社"
            )

        with col2:
            news_date = st.date_input(
                "发布日期",
                value=datetime.now()
            )

        submitted = st.form_submit_button("💾 保存新闻", use_container_width=True)

        if submitted:
            if not news_title or not news_content:
                st.error("❌ 请填写标题和内容")
            else:
                with st.spinner("正在生成 Embedding 并保存..."):
                    try:
                        result = api_client.add_news(
                            title=news_title,
                            content=news_content,
                            source=news_source or None
                        )

                        st.success(f"✅ 新闻添加成功！ID: {result['news_id']}")
                        st.balloons()

                        # 清除缓存
                        st.cache_data.clear()

                        # 清空表单（通过重新运行）
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ 添加失败: {str(e)}")

st.markdown("---")

# 语义搜索（未来功能）
st.markdown("### 🔍 语义搜索")
st.info("🚧 此功能正在开发中，将支持基于向量相似度的智能搜索")

with st.expander("预览功能"):
    search_query = st.text_input(
        "搜索关键词",
        placeholder="例如：加密货币市场趋势",
        disabled=True
    )

    search_limit = st.slider(
        "返回结果数量",
        min_value=1,
        max_value=20,
        value=5,
        disabled=True
    )

    if st.button("🔍 搜索", disabled=True):
        st.warning("功能开发中...")

# 使用说明
with st.expander("ℹ️ 使用说明"):
    st.markdown("""
    ### 市场新闻管理

    1. **添加新闻**:
       - 填写新闻标题和内容
       - 系统会自动使用 OpenAI 生成 Embedding
       - Embedding 存储在 pgvector 中，用于语义检索

    2. **AI 分析集成**:
       - 当您在「AI 分析」页面提问时
       - 系统会自动检索相关新闻
       - 基于向量相似度找到最相关的市场信息

    3. **数据来源建议**:
       - 财经新闻网站
       - 交易所公告
       - 行业研究报告
       - 市场分析文章

    4. **最佳实践**:
       - 定期更新市场新闻
       - 标注准确的新闻来源
       - 内容尽量详细完整
       - 避免重复添加相同新闻
    """)
