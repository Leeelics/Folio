import streamlit as st
from api_client import FolioAPIClient
import os

st.set_page_config(
    page_title="Folio - 个人财务管理系统",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return FolioAPIClient(base_url=api_url)


api_client = get_api_client()


def format_currency(amount, currency="CNY"):
    symbols = {"CNY": "¥", "USD": "$", "HKD": "HK$"}
    symbol = symbols.get(currency, currency)
    return f"{symbol}{float(amount or 0):,.2f}"


# 侧边栏
with st.sidebar:
    st.title("💰 Folio")
    st.markdown("---")
    st.markdown("### 个人财务管理系统")
    st.markdown(
        """
    - 📊 资产总览
    - 💰 账户管理
    - 📅 预算管理
    - 📝 日常记账
    - 📈 投资组合
    - 📝 交易录入
    """
    )
    st.markdown("---")

    try:
        health = api_client.health_check()
        st.success(f"后端状态: {health.get('status', 'unknown')}")
    except Exception as e:
        st.error(f"后端连接失败: {str(e)}")

# 主页面
st.title("Folio")
st.markdown("个人财务管理系统")

# 核心指标
st.markdown("---")

try:
    dashboard = api_client.get_dashboard()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("净资产", format_currency(dashboard.get("net_worth", 0)))
    with col2:
        st.metric("总资产", format_currency(dashboard.get("total_assets", 0)))
    with col3:
        st.metric("总负债", format_currency(dashboard.get("total_liability", 0)))
    with col4:
        st.metric("本月支出", format_currency(dashboard.get("monthly_expense_total", 0)))

    # 活跃预算概览
    active_budgets = dashboard.get("active_budgets", [])
    if active_budgets:
        st.markdown("---")
        st.markdown("### 预算概览")
        for budget in active_budgets:
            amount = float(budget.get("amount", 0) or 0)
            spent = float(budget.get("spent", 0) or 0)
            progress = (spent / amount) if amount > 0 else 0
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.write(f"**{budget['name']}**")
                st.progress(min(progress, 1.0))
            with col_b:
                st.write(f"{format_currency(spent)} / {format_currency(amount)}")

except Exception as e:
    st.error(f"无法加载数据: {str(e)}")
    st.info("请确保后端服务正在运行。")

# 快速导航
st.markdown("---")
st.markdown("### 快速导航")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**📊 资产总览**")
    st.caption("数据看板与图表分析")
    if st.button("进入", key="nav_overview"):
        st.switch_page("pages/1_Assets.py")

with col2:
    st.markdown("**💰 账户管理**")
    st.caption("资产、负债、转账")
    if st.button("进入", key="nav_accounts"):
        st.switch_page("pages/2_Accounts.py")

with col3:
    st.markdown("**📅 预算管理**")
    st.caption("预算计划与跟踪")
    if st.button("进入", key="nav_budgets"):
        st.switch_page("pages/3_Budgets.py")

col4, col5, col6 = st.columns(3)

with col4:
    st.markdown("**📝 日常记账**")
    st.caption("记录日常消费")
    if st.button("进入", key="nav_expenses"):
        st.switch_page("pages/4_Expenses.py")

with col5:
    st.markdown("**📈 投资组合**")
    st.caption("持仓分布与盈亏分析")
    if st.button("进入", key="nav_portfolio"):
        st.switch_page("pages/5_Portfolio.py")

with col6:
    st.markdown("**📝 交易录入**")
    st.caption("买入、卖出、分红")
    if st.button("进入", key="nav_trading"):
        st.switch_page("pages/6_Trades.py")

# 页脚
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "<p>Folio v2.0 | FastAPI + Streamlit</p>"
    "</div>",
    unsafe_allow_html=True,
)
