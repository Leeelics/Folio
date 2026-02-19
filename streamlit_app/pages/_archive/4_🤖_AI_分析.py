import streamlit as st
import sys
import os
from datetime import datetime

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import EquilibraAPIClient

st.set_page_config(page_title="AI 分析", page_icon="🤖", layout="wide")

# 初始化 API 客户端
@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return EquilibraAPIClient(base_url=api_url)

api_client = get_api_client()

st.title("🤖 AI 智能分析")
st.markdown("基于 LangGraph 的智能投资顾问，结合市场新闻和资产状况提供专业建议")
st.markdown("---")

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []

if "analysis_history" not in st.session_state:
    st.session_state.analysis_history = []

# 侧边栏 - 当前资产状况
with st.sidebar:
    st.markdown("### 📊 当前资产状况")

    try:
        portfolio = api_client.get_portfolio_status()

        st.metric(
            "总资产",
            f"¥{portfolio['total_assets']:,.0f}"
        )

        wedding_finance = portfolio['wedding_finance']
        st.metric(
            "安全边际",
            f"{wedding_finance['margin_percentage']:.1f}%"
        )

        risk_level = wedding_finance['risk_level']
        risk_colors = {
            "LOW": "🟢",
            "MEDIUM": "🟡",
            "HIGH": "🟠",
            "CRITICAL": "🔴"
        }
        st.markdown(f"**风险等级**: {risk_colors.get(risk_level, '⚪')} {risk_level}")

        st.markdown("---")
        st.markdown("### 💡 快速问题")

        quick_questions = [
            "分析当前市场情况并给出投资建议",
            "我的资产配置是否合理？",
            "现在适合增加加密货币投资吗？",
            "如何在保证婚礼预算的前提下提高收益？",
            "当前有哪些风险需要注意？"
        ]

        for q in quick_questions:
            if st.button(q, key=f"quick_{q}", use_container_width=True):
                st.session_state.current_query = q

    except Exception as e:
        st.error(f"无法加载资产数据: {str(e)}")

# 主界面 - AI 对话
st.markdown("### 💬 与 AI 顾问对话")

# 显示历史消息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # 如果是 AI 回复，显示相关新闻
        if message["role"] == "assistant" and "news" in message:
            with st.expander("📰 参考的市场新闻"):
                for news in message["news"]:
                    st.markdown(f"""
                    **{news['title']}** (相似度: {news['similarity']:.2f})

                    {news['content'][:200]}...
                    """)

# 聊天输入
if prompt := st.chat_input("输入您的问题..."):
    # 添加用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # 调用 AI 分析
    with st.chat_message("assistant"):
        with st.spinner("AI 正在分析中..."):
            try:
                # 调用后端 API
                result = api_client.agent_analyze(query=prompt, news_limit=5)

                # 显示 AI 回复
                analysis = result.get("analysis", "抱歉，无法生成分析。")
                st.markdown(analysis)

                # 保存消息
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": analysis,
                    "news": result.get("relevant_news", []),
                    "timestamp": datetime.now().isoformat()
                })

                # 显示相关新闻
                if result.get("relevant_news"):
                    with st.expander("📰 参考的市场新闻"):
                        for news in result["relevant_news"]:
                            st.markdown(f"""
                            **{news['title']}** (相似度: {news['similarity']:.2f})

                            {news['content'][:200]}...
                            """)

                # 显示系统建议
                if result.get("recommendations"):
                    st.markdown("---")
                    st.markdown("**💡 系统建议:**")
                    for rec in result["recommendations"]:
                        st.info(rec)

            except Exception as e:
                error_msg = f"❌ AI 分析失败: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg
                })

# 处理快速问题
if "current_query" in st.session_state:
    query = st.session_state.current_query
    del st.session_state.current_query

    # 添加用户消息
    st.session_state.messages.append({"role": "user", "content": query})

    # 调用 AI 分析
    with st.spinner("AI 正在分析中..."):
        try:
            result = api_client.agent_analyze(query=query, news_limit=5)
            analysis = result.get("analysis", "抱歉，无法生成分析。")

            st.session_state.messages.append({
                "role": "assistant",
                "content": analysis,
                "news": result.get("relevant_news", []),
                "timestamp": datetime.now().isoformat()
            })

            st.rerun()

        except Exception as e:
            st.error(f"❌ AI 分析失败: {str(e)}")

# 清除对话历史
st.markdown("---")
col1, col2 = st.columns([5, 1])

with col2:
    if st.button("🗑️ 清除历史", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# 使用说明
with st.expander("ℹ️ 使用说明"):
    st.markdown("""
    ### 如何使用 AI 智能分析

    1. **提问方式**:
       - 直接输入您的问题，例如："当前适合投资什么？"
       - 使用侧边栏的快速问题按钮

    2. **AI 分析内容**:
       - 结合您的资产状况
       - 参考最新市场新闻（通过向量相似度检索）
       - 考虑婚礼预算约束
       - 提供风险提示

    3. **建议类型**:
       - 资产配置建议
       - 止盈止损策略
       - 风险控制措施
       - 投资时机判断

    4. **注意事项**:
       - AI 建议仅供参考，不构成投资建议
       - 请结合自身情况谨慎决策
       - 建议定期与 AI 对话，跟踪市场变化
    """)
