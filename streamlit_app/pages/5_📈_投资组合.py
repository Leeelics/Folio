"""
投资组合页面 - 持仓分布、盈亏分析、市值同步
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import FolioAPIClient

st.set_page_config(page_title="投资组合", page_icon="📈", layout="wide")


@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return FolioAPIClient(base_url=api_url)


api_client = get_api_client()

st.title("📈 投资组合")
st.markdown("---")


def format_currency(amount, currency="CNY"):
    symbols = {"CNY": "¥", "USD": "$", "HKD": "HK$"}
    symbol = symbols.get(currency, currency)
    return f"{symbol}{float(amount or 0):,.2f}"


def format_pct(val):
    v = float(val or 0)
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}%"


# ============ Sidebar ============
with st.sidebar:
    st.header("📈 投资组合")
    if st.button("同步市值", use_container_width=True):
        try:
            result = api_client.sync_holdings_value()
            st.success(f"同步完成: {result.get('message', 'OK')}")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"同步失败: {e}")

# ============ Portfolio Overview ============
try:
    portfolio = api_client.get_portfolio()
except Exception as e:
    st.error(f"加载投资组合失败: {e}")
    st.info("请确保后端服务正在运行。")
    st.stop()

total_value = portfolio.get("total_value", 0)
holdings = portfolio.get("holdings", [])
holdings_count = portfolio.get("holdings_count", len(holdings))

# ============ PnL Analysis ============
try:
    pnl_data = api_client.get_pnl_analysis()
except Exception:
    pnl_data = {"total_cost": 0, "total_value": 0, "total_pnl": 0, "total_pnl_pct": 0, "holdings": []}

total_cost = pnl_data.get("total_cost", 0)
total_pnl = pnl_data.get("total_pnl", 0)
total_pnl_pct = pnl_data.get("total_pnl_pct", 0)

# ============ Key Metrics ============
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("总市值", format_currency(total_value))
with col2:
    st.metric("总成本", format_currency(total_cost))
with col3:
    st.metric("总盈亏", format_currency(total_pnl), delta=format_pct(total_pnl_pct))
with col4:
    st.metric("持仓数量", holdings_count)

st.markdown("---")

if not holdings:
    st.info("暂无持仓数据。请先在交易录入页面添加交易，或在账户管理中添加持仓。")
    st.stop()

# ============ Allocation Pie Chart ============
col_chart, col_table = st.columns([1, 1])

with col_chart:
    st.subheader("持仓分布")
    chart_data = [
        {"名称": h.get("name", h["symbol"]), "市值": h.get("market_value", 0)}
        for h in holdings
        if h.get("market_value", 0) > 0
    ]
    if chart_data:
        df_chart = pd.DataFrame(chart_data)
        fig = px.pie(
            df_chart,
            values="市值",
            names="名称",
            hole=0.4,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("无有效市值数据用于绘制图表")

with col_table:
    st.subheader("持仓明细")
    table_data = []
    for h in holdings:
        table_data.append({
            "代码": h["symbol"],
            "名称": h.get("name", ""),
            "类型": h.get("asset_type", ""),
            "数量": h.get("quantity", 0),
            "现价": h.get("current_price", 0),
            "市值": h.get("market_value", 0),
            "占比": f"{h.get('allocation_pct', 0):.1f}%",
        })
    df_table = pd.DataFrame(table_data)
    st.dataframe(
        df_table,
        column_config={
            "数量": st.column_config.NumberColumn("数量", format="%.4f"),
            "现价": st.column_config.NumberColumn("现价", format="%.4f"),
            "市值": st.column_config.NumberColumn("市值", format="%.2f"),
        },
        hide_index=True,
        use_container_width=True,
    )

# ============ PnL Table ============
st.markdown("---")
st.subheader("盈亏分析")

pnl_holdings = pnl_data.get("holdings", [])
if pnl_holdings:
    pnl_table = []
    for h in pnl_holdings:
        pnl_val = h.get("pnl", 0)
        pnl_table.append({
            "代码": h["symbol"],
            "名称": h.get("name", ""),
            "数量": h.get("quantity", 0),
            "成本价": h.get("avg_cost", 0),
            "现价": h.get("current_price", 0),
            "成本": h.get("cost_basis", 0),
            "现值": h.get("current_value", 0),
            "盈亏": pnl_val,
            "盈亏率": format_pct(h.get("pnl_pct", 0)),
        })
    df_pnl = pd.DataFrame(pnl_table)
    st.dataframe(
        df_pnl,
        column_config={
            "数量": st.column_config.NumberColumn("数量", format="%.4f"),
            "成本价": st.column_config.NumberColumn("成本价", format="%.4f"),
            "现价": st.column_config.NumberColumn("现价", format="%.4f"),
            "成本": st.column_config.NumberColumn("成本", format="%.2f"),
            "现值": st.column_config.NumberColumn("现值", format="%.2f"),
            "盈亏": st.column_config.NumberColumn("盈亏", format="%.2f"),
        },
        hide_index=True,
        use_container_width=True,
    )
else:
    st.info("暂无盈亏数据（需要通过交易录入页面创建交易记录）")
