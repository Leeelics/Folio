import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import sys
import os
import logging

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import EquilibraAPIClient

logger = logging.getLogger(__name__)

st.set_page_config(page_title="资产总览", page_icon="📊", layout="wide")


# 初始化 API 客户端
@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return EquilibraAPIClient(base_url=api_url)


api_client = get_api_client()

st.title("📊 资产总览")
st.markdown("---")

# 刷新按钮
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🔄 刷新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# 获取资产数据
@st.cache_data(ttl=60)
def load_portfolio_data():
    return api_client.get_portfolio_status()


@st.cache_data(ttl=60)
def load_stock_summary():
    try:
        return api_client.get_positions_summary()
    except:
        return None


@st.cache_data(ttl=60)
def load_brokerage_summary():
    """加载新平台账户系统的资产汇总"""
    try:
        return api_client.get_brokerage_summary()
    except Exception as e:
        logger.warning(f"加载新系统资产汇总失败: {e}")
        return None


@st.cache_data(ttl=60)
def load_brokerage_allocation():
    """加载新平台账户系统的资产分配"""
    try:
        return api_client.get_brokerage_allocation()
    except Exception as e:
        logger.warning(f"加载新系统资产分配失败: {e}")
        return None


try:
    portfolio = load_portfolio_data()
    stock_summary = load_stock_summary()
    brokerage_summary = load_brokerage_summary()
    brokerage_allocation = load_brokerage_allocation()

    # 关键指标卡片
    st.markdown("### 📈 关键指标")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # 优先显示新系统的总资产
        total_assets = (
            brokerage_summary["total_assets_cny"]
            if brokerage_summary
            else portfolio["total_assets"]
        )
        st.metric(label="💰 总资产", value=f"¥{total_assets:,.2f}")

    with col2:
        wedding_finance = portfolio["wedding_finance"]
        st.metric(label="💍 婚礼预算剩余", value=f"¥{wedding_finance['remaining_budget']:,.2f}")

    with col3:
        st.metric(label="🛡️ 安全边际", value=f"{wedding_finance['margin_percentage']:.1f}%")

    with col4:
        st.metric(label="💵 可投资金额", value=f"¥{wedding_finance['investable_amount']:,.2f}")

    # 股票持仓快速概览
    if stock_summary and stock_summary.get("position_count", 0) > 0:
        st.markdown("---")
        st.markdown("### 📈 股票持仓概览")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(label="股票市值", value=f"¥{stock_summary.get('total_current_cny', 0):,.2f}")

        with col2:
            st.metric(label="股票成本", value=f"¥{stock_summary.get('total_cost_cny', 0):,.2f}")

        with col3:
            pnl = stock_summary.get("total_pnl_cny", 0)
            pnl_pct = stock_summary.get("total_pnl_percent", 0)
            st.metric(label="股票盈亏", value=f"¥{pnl:,.2f}", delta=f"{pnl_pct:+.2f}%")

        with col4:
            st.metric(label="持仓数量", value=f"{stock_summary.get('position_count', 0)} 只")

        # 快速入口
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📈 查看股票行情", use_container_width=True):
                st.switch_page("pages/6_📈_股票行情.py")
        with col2:
            if st.button("💼 管理股票持仓", use_container_width=True):
                st.switch_page("pages/7_💼_股票持仓.py")

    st.markdown("---")

    # 资产分布
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("### 🥧 资产分布")

        # 准备饼图数据
        allocation = portfolio["allocation"]
        labels = list(allocation.keys())
        values = [allocation[key]["value"] for key in labels]
        percentages = [allocation[key]["percentage"] for key in labels]

        # 创建饼图
        fig = go.Figure(
            data=[
                go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.4,
                    textinfo="label+percent",
                    textposition="outside",
                    marker=dict(
                        colors=px.colors.qualitative.Set3, line=dict(color="white", width=2)
                    ),
                )
            ]
        )

        fig.update_layout(showlegend=True, height=400, margin=dict(t=20, b=20, l=20, r=20))

        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### 📋 账户明细")

        # 显示各账户详情
        for account_type, info in allocation.items():
            with st.expander(f"{account_type} - ¥{info['value']:,.2f} ({info['percentage']:.1f}%)"):
                for account in info["accounts"]:
                    st.markdown(f"""
                    - **{account["name"]}**: {account["balance"]:,.2f} {account["currency"]}
                    """)

    st.markdown("---")

    # 婚礼金安全水位
    st.markdown("### 💍 婚礼金安全水位")

    col1, col2 = st.columns([2, 1])

    with col1:
        # 创建进度条可视化
        wedding_finance = portfolio["wedding_finance"]
        total_budget = wedding_finance["wedding_budget"]
        spent = wedding_finance["spent"]
        remaining = wedding_finance["remaining_budget"]

        # 计算百分比
        spent_pct = (spent / total_budget) * 100 if total_budget > 0 else 0
        remaining_pct = (remaining / total_budget) * 100 if total_budget > 0 else 0

        # 创建堆叠条形图
        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                name="已支出",
                x=[spent],
                y=["婚礼预算"],
                orientation="h",
                marker=dict(color="#FF6B6B"),
                text=f"¥{spent:,.0f}",
                textposition="inside",
            )
        )

        fig.add_trace(
            go.Bar(
                name="剩余预算",
                x=[remaining],
                y=["婚礼预算"],
                orientation="h",
                marker=dict(color="#4ECDC4"),
                text=f"¥{remaining:,.0f}",
                textposition="inside",
            )
        )

        fig.update_layout(
            barmode="stack",
            height=150,
            showlegend=True,
            margin=dict(t=20, b=20, l=100, r=20),
            xaxis=dict(title="金额 (CNY)"),
            yaxis=dict(title=""),
        )

        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### 📊 预算详情")
        st.markdown(f"""
        - **总预算**: ¥{total_budget:,.2f}
        - **已支出**: ¥{spent:,.2f}
        - **剩余**: ¥{remaining:,.2f}
        - **距离婚礼**: {wedding_finance["days_until_wedding"]} 天
        """)

        # 风险等级显示
        risk_level = wedding_finance["risk_level"]
        risk_colors = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}
        st.markdown(f"**风险等级**: {risk_colors.get(risk_level, '⚪')} {risk_level}")

    st.markdown("---")

    # 系统建议
    st.markdown("### 💡 系统建议")
    for rec in portfolio.get("recommendations", []):
        st.info(rec)

    # ============ 新系统：平台账户资产分布 ============
    if brokerage_summary and brokerage_summary.get("accounts"):
        st.markdown("---")
        st.markdown("### 🏦 平台账户资产分布（新系统）")

        # 账户资产表格
        account_data = []
        for account in brokerage_summary["accounts"]:
            account_data.append(
                {
                    "账户名称": account["account_name"],
                    "类型": account["platform_type"],
                    "机构": account.get("institution", "-"),
                    "现金": f"¥{account['cash_cny']:,.2f}",
                    "持仓": f"¥{account['holdings_cny']:,.2f}",
                    "总资产": f"¥{account['total_cny']:,.2f}",
                }
            )

        if account_data:
            st.dataframe(pd.DataFrame(account_data), use_container_width=True, hide_index=True)

        # 资产分配饼图
        if brokerage_allocation:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### 按平台类型分布")
                if brokerage_allocation.get("by_platform_type"):
                    labels = list(brokerage_allocation["by_platform_type"].keys())
                    values = list(brokerage_allocation["by_platform_type"].values())

                    fig = go.Figure(
                        data=[
                            go.Pie(
                                labels=labels,
                                values=values,
                                hole=0.4,
                                textinfo="label+percent",
                                textposition="outside",
                            )
                        ]
                    )
                    fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
                    st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.markdown("#### 按资产类型分布")
                if brokerage_allocation.get("by_asset_type"):
                    labels = list(brokerage_allocation["by_asset_type"].keys())
                    values = list(brokerage_allocation["by_asset_type"].values())

                    fig = go.Figure(
                        data=[
                            go.Pie(
                                labels=labels,
                                values=values,
                                hole=0.4,
                                textinfo="label+percent",
                                textposition="outside",
                            )
                        ]
                    )
                    fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
                    st.plotly_chart(fig, use_container_width=True)

        # 快速入口
        st.markdown("#### 快速操作")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💰 管理平台账户", use_container_width=True):
                st.switch_page("pages/2_💰_账户管理.py")
        with col2:
            if st.button("➕ 添加新账户", use_container_width=True):
                st.switch_page("pages/2_💰_账户管理.py")

except Exception as e:
    st.error(f"❌ 无法加载资产数据: {str(e)}")
    st.info("请确保后端服务正在运行。")
