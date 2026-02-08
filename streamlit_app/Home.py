import streamlit as st
from api_client import EquilibraAPIClient
import os

# 页面配置
st.set_page_config(
    page_title="Equilibra - 个人财务管理系统",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化 API 客户端
@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return EquilibraAPIClient(base_url=api_url)

api_client = get_api_client()

# 侧边栏
with st.sidebar:
    st.title("💰 Equilibra")
    st.markdown("---")
    st.markdown("### 个人财务管理系统")
    st.markdown("""
    - 📊 资产总览
    - 💰 账户管理
    - 📈 交易流水
    - 🤖 AI 分析
    - 📰 市场新闻
    """)
    st.markdown("---")

    # 健康检查
    try:
        health = api_client.health_check()
        st.success(f"✅ 后端状态: {health.get('status', 'unknown')}")
    except Exception as e:
        st.error(f"❌ 后端连接失败: {str(e)}")

# 主页面
st.title("🏠 欢迎使用 Equilibra")
st.markdown("### 个人财务管理系统 - 智能资产配置与风险控制")

# 快速概览
st.markdown("---")
st.markdown("## 📊 快速概览")

try:
    # 获取资产组合状态
    portfolio = api_client.get_portfolio_status()

    # 显示关键指标
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="总资产",
            value=f"¥{portfolio['total_assets']:,.2f}",
            delta=None
        )

    with col2:
        wedding_finance = portfolio['wedding_finance']
        st.metric(
            label="婚礼预算剩余",
            value=f"¥{wedding_finance['remaining_budget']:,.2f}",
            delta=None
        )

    with col3:
        st.metric(
            label="安全边际",
            value=f"{wedding_finance['margin_percentage']:.1f}%",
            delta=None,
            delta_color="normal"
        )

    with col4:
        risk_level = wedding_finance['risk_level']
        risk_color = {
            "LOW": "🟢",
            "MEDIUM": "🟡",
            "HIGH": "🟠",
            "CRITICAL": "🔴"
        }
        st.metric(
            label="风险等级",
            value=f"{risk_color.get(risk_level, '⚪')} {risk_level}",
            delta=None
        )

    # 显示建议
    st.markdown("### 💡 系统建议")
    for rec in portfolio.get('recommendations', []):
        st.info(rec)

    # 距离婚礼天数
    days_until = wedding_finance.get('days_until_wedding', 0)
    if days_until > 0:
        st.markdown(f"### ⏰ 距离婚礼还有 **{days_until}** 天")

except Exception as e:
    st.error(f"无法加载资产数据: {str(e)}")
    st.info("请确保后端服务正在运行，并检查 API 连接配置。")

# 功能导航
st.markdown("---")
st.markdown("## 🚀 快速导航")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📊 资产总览")
    st.markdown("查看资产分布、账户明细和历史趋势")
    if st.button("进入资产总览", key="nav_assets"):
        st.switch_page("pages/1_📊_资产总览.py")

with col2:
    st.markdown("### 🤖 AI 分析")
    st.markdown("获取智能投资建议和风险提示")
    if st.button("进入 AI 分析", key="nav_ai"):
        st.switch_page("pages/4_🤖_AI_分析.py")

with col3:
    st.markdown("### 📈 交易流水")
    st.markdown("查看交易记录和婚礼支出")
    if st.button("进入交易流水", key="nav_transactions"):
        st.switch_page("pages/3_📈_交易流水.py")

# 页脚
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>Equilibra v1.0.0 | Powered by FastAPI + Streamlit + LangGraph</p>
</div>
""", unsafe_allow_html=True)
