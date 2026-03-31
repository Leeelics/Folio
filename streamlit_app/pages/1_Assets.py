"""
资产总览页面 - 完整财务仪表盘
"""

import streamlit as st
import plotly.express as px
import pandas as pd
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import FolioAPIClient

st.set_page_config(page_title="资产总览", page_icon="📊", layout="wide")


@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return FolioAPIClient(base_url=api_url)


api_client = get_api_client()

st.title("📊 资产总览")
st.markdown("---")


def format_currency(amount, currency="CNY"):
    symbols = {"CNY": "¥", "USD": "$", "HKD": "HK$"}
    symbol = symbols.get(currency, currency)
    return f"{symbol}{float(amount or 0):,.2f}"


def _f(val):
    return float(val or 0)


# ============ 刷新按钮 ============
if st.button("🔄 刷新"):
    st.cache_data.clear()
    st.rerun()


# ============ 关键指标 ============
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


# ============ 资产分布图表 ============
st.markdown("---")
col_left, col_right = st.columns(2)

accounts = api_client.get_accounts()

with col_left:
    st.subheader("资产分布")
    cash_total = sum(_f(a.get("balance", 0)) for a in accounts if a["account_type"] == "cash")
    investment_total = sum(_f(a.get("total_value", 0)) for a in accounts if a["account_type"] == "investment")
    
    df_dist = pd.DataFrame({
        "类型": ["现金账户", "投资账户"],
        "金额": [cash_total, investment_total]
    })
    fig_dist = px.pie(df_dist, values="金额", names="类型", hole=0.4)
    st.plotly_chart(fig_dist, use_container_width=True)

with col_right:
    st.subheader("账户余额")
    df_accounts = pd.DataFrame([{
        "账户": a["name"],
        "余额": _f(a.get("total_value") if a["account_type"] == "investment" else a.get("balance"))
    } for a in accounts])
    fig_bar = px.bar(df_accounts, x="账户", y="余额")
    st.plotly_chart(fig_bar, use_container_width=True)


# ============ 负债概览 ============
st.markdown("---")
st.subheader("💳 负债概览")

liabilities = api_client.get_liabilities()
if liabilities:
    for lib in liabilities:
        col_a, col_b, col_c = st.columns([2, 1, 1])
        with col_a:
            st.write(f"**{lib['name']}**")
        with col_b:
            st.write(f"剩余: {format_currency(lib.get('remaining_amount', 0))}")
        with col_c:
            st.write(f"月供: {format_currency(lib.get('monthly_payment', 0))}")
else:
    st.info("暂无负债")


# ============ 支出分析图表 ============
st.markdown("---")
col_trend, col_category = st.columns(2)

expenses = api_client.get_expenses()

# 防御性处理：确保费用数据有日期字段
def get_expense_date(e):
    """获取费用日期，支持 expense_date 或 date 字段"""
    date_str = e.get("expense_date") or e.get("date")
    if date_str:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return None

with col_trend:
    st.subheader("月度支出趋势")
    six_months_ago = datetime.now() - timedelta(days=180)
    recent_expenses = [e for e in expenses if get_expense_date(e) and get_expense_date(e) >= six_months_ago]
    
    df_expenses = pd.DataFrame(recent_expenses)
    if not df_expenses.empty:
        # 使用 expense_date 或 date 字段
        date_col = "expense_date" if "expense_date" in df_expenses.columns else "date"
        df_expenses["month"] = pd.to_datetime(df_expenses[date_col]).dt.to_period("M").astype(str)
        df_monthly = df_expenses.groupby("month")["amount"].sum().reset_index()
        fig_trend = px.line(df_monthly, x="month", y="amount", markers=True)
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("暂无支出数据")

with col_category:
    st.subheader("本月支出分类")
    current_month = datetime.now().replace(day=1)
    month_expenses = [e for e in expenses if get_expense_date(e) and get_expense_date(e) >= current_month]
    
    if month_expenses:
        df_category = pd.DataFrame(month_expenses).groupby("category")["amount"].sum().reset_index()
        fig_category = px.pie(df_category, values="amount", names="category")
        st.plotly_chart(fig_category, use_container_width=True)
    else:
        st.info("本月暂无支出")


# ============ 预算执行 ============
st.markdown("---")
st.subheader("📅 预算执行")

budgets = dashboard.get("active_budgets", [])
if budgets:
    for budget in budgets:
        amount = _f(budget.get("amount", 0))
        spent = _f(budget.get("spent", 0))
        progress = (spent / amount * 100) if amount > 0 else 0
        
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.write(f"**{budget['name']}**")
            st.progress(min(progress / 100, 1.0))
        with col_b:
            st.write(f"{format_currency(spent)} / {format_currency(amount)}")
else:
    st.info("暂无进行中的预算")


# ============ 快捷操作 ============
st.markdown("---")
st.subheader("⚡ 快捷操作")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.page_link("pages/4_Expenses.py", label="📝 日常记账")
with col2:
    st.page_link("pages/2_Accounts.py", label="💰 账户管理")
with col3:
    st.page_link("pages/3_Budgets.py", label="📅 预算管理")
with col4:
    st.page_link("pages/1_Assets.py", label="📊 资产总览")
