"""股票持仓页面 - 持仓管理、盈亏计算"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from streamlit_app.api_client import EquilibraAPIClient

st.set_page_config(page_title="股票持仓 - Equilibra", page_icon="💼", layout="wide")

# 初始化 API 客户端
@st.cache_resource
def get_api_client():
    return EquilibraAPIClient()

client = get_api_client()

st.title("💼 股票持仓")
st.markdown("管理股票持仓，跟踪盈亏情况")

# ============ 持仓汇总 ============
st.header("持仓汇总")

try:
    summary = client.get_positions_summary()

    if summary and "error" not in summary:
        col1, col2, col3, col4 = st.columns(4)

        total_current = summary.get('total_current_cny', 0)
        total_cost = summary.get('total_cost_cny', 0)
        total_pnl = summary.get('total_pnl_cny', 0)
        total_pnl_pct = summary.get('total_pnl_percent', 0)

        with col1:
            st.metric("总市值", f"¥{total_current:,.2f}")

        with col2:
            st.metric("总成本", f"¥{total_cost:,.2f}")

        with col3:
            pnl_delta = f"{total_pnl_pct:+.2f}%"
            st.metric("总盈亏", f"¥{total_pnl:,.2f}", delta=pnl_delta)

        with col4:
            st.metric("持仓数量", f"{summary.get('position_count', 0)} 只")

        # 按市场分布饼图
        by_market = summary.get('by_market', {})
        if by_market:
            st.subheader("市场分布")

            col1, col2 = st.columns([1, 2])

            with col1:
                # 饼图数据
                labels = list(by_market.keys())
                values = [by_market[m]['current_cny'] for m in labels]

                fig = go.Figure(data=[go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.4,
                    textinfo='label+percent',
                    marker=dict(colors=px.colors.qualitative.Set2)
                )])
                fig.update_layout(
                    title="持仓市值分布",
                    showlegend=True,
                    height=300
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # 市场明细表
                market_data = []
                for market, data in by_market.items():
                    market_data.append({
                        "市场": market,
                        "市值(CNY)": f"¥{data['current_cny']:,.2f}",
                        "成本(CNY)": f"¥{data['cost_cny']:,.2f}",
                        "盈亏(CNY)": f"¥{data['pnl_cny']:,.2f}",
                        "持仓数": data['position_count']
                    })

                if market_data:
                    st.dataframe(pd.DataFrame(market_data), use_container_width=True, hide_index=True)
    else:
        st.info("暂无持仓数据")
except Exception as e:
    st.warning(f"获取持仓汇总失败: {e}")

st.divider()

# ============ 添加持仓 ============
st.header("添加持仓")

with st.expander("添加新持仓", expanded=False):
    col1, col2 = st.columns(2)

    with col1:
        new_symbol = st.text_input("股票代码", placeholder="如: 600000, 00700, AAPL")
        new_market = st.selectbox("市场", ["A股", "港股", "美股"])
        new_account = st.text_input("账户名称", value="默认账户", placeholder="如: 华泰证券")

    with col2:
        new_quantity = st.number_input("持仓数量", min_value=1, value=100, step=100)
        new_cost_price = st.number_input("成本价", min_value=0.01, value=10.0, step=0.01, format="%.4f")
        new_notes = st.text_input("备注", placeholder="可选")

    if st.button("添加持仓", type="primary"):
        if new_symbol and new_quantity > 0 and new_cost_price > 0:
            try:
                result = client.add_position(
                    symbol=new_symbol,
                    market=new_market,
                    quantity=new_quantity,
                    cost_price=new_cost_price,
                    account_name=new_account,
                    notes=new_notes
                )
                if result and "error" not in result:
                    st.success(f"已添加持仓: {new_symbol}")
                    st.rerun()
                else:
                    st.error("添加失败")
            except Exception as e:
                st.error(f"添加失败: {e}")
        else:
            st.warning("请填写完整的持仓信息")

st.divider()

# ============ 持仓列表 ============
st.header("持仓明细")

try:
    positions_data = client.get_positions()

    if positions_data and "positions" in positions_data and len(positions_data["positions"]) > 0:
        positions = positions_data["positions"]

        # 按市场分组显示
        markets = set(p["market"] for p in positions)

        for market in sorted(markets):
            market_positions = [p for p in positions if p["market"] == market]

            with st.expander(f"{market} ({len(market_positions)} 只)", expanded=True):
                for pos in market_positions:
                    # 获取实时盈亏
                    try:
                        pnl_data = client.get_position_pnl(pos["id"])
                    except:
                        pnl_data = None

                    col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 1, 1, 2, 1])

                    with col1:
                        name = pos.get('name') or pos.get('symbol')
                        st.write(f"**{name}**")
                        st.caption(f"{pos.get('symbol')} | {pos.get('account_name', '默认账户')}")

                    with col2:
                        st.write(f"{pos.get('quantity')} 股")
                        st.caption("持仓数量")

                    with col3:
                        st.write(f"¥{pos.get('cost_price', 0):.2f}")
                        st.caption("成本价")

                    with col4:
                        if pnl_data and "current_price" in pnl_data:
                            current_price = pnl_data.get('current_price', 0)
                            change_today = pnl_data.get('change_today', 0)
                            color = "red" if change_today > 0 else ("green" if change_today < 0 else "gray")
                            st.markdown(f"¥{current_price:.2f}")
                            st.caption(f"现价 ({change_today:+.2f}%)")
                        else:
                            st.write("--")
                            st.caption("现价")

                    with col5:
                        if pnl_data and "pnl_cny" in pnl_data:
                            pnl = pnl_data.get('pnl_cny', 0)
                            pnl_pct = pnl_data.get('pnl_percent', 0)
                            color = "red" if pnl > 0 else ("green" if pnl < 0 else "gray")
                            st.markdown(f"<span style='color:{color}'>¥{pnl:,.2f} ({pnl_pct:+.2f}%)</span>",
                                       unsafe_allow_html=True)
                            st.caption("盈亏")
                        else:
                            st.write("--")
                            st.caption("盈亏")

                    with col6:
                        col_edit, col_del = st.columns(2)
                        with col_edit:
                            if st.button("编辑", key=f"edit_{pos['id']}", use_container_width=True):
                                st.session_state[f"editing_{pos['id']}"] = True

                        with col_del:
                            if st.button("删除", key=f"del_{pos['id']}", use_container_width=True):
                                try:
                                    client.delete_position(pos['id'])
                                    st.success("已删除")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"删除失败: {e}")

                    # 编辑表单
                    if st.session_state.get(f"editing_{pos['id']}", False):
                        with st.form(key=f"edit_form_{pos['id']}"):
                            st.subheader(f"编辑 {pos.get('symbol')}")
                            edit_col1, edit_col2 = st.columns(2)

                            with edit_col1:
                                edit_quantity = st.number_input(
                                    "持仓数量",
                                    min_value=0,
                                    value=pos.get('quantity', 0),
                                    key=f"edit_qty_{pos['id']}"
                                )

                            with edit_col2:
                                edit_cost = st.number_input(
                                    "成本价",
                                    min_value=0.0,
                                    value=float(pos.get('cost_price', 0)),
                                    format="%.4f",
                                    key=f"edit_cost_{pos['id']}"
                                )

                            col_save, col_cancel = st.columns(2)
                            with col_save:
                                if st.form_submit_button("保存", type="primary"):
                                    try:
                                        client.update_position(
                                            pos['id'],
                                            quantity=edit_quantity,
                                            cost_price=edit_cost
                                        )
                                        st.session_state[f"editing_{pos['id']}"] = False
                                        st.success("已更新")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"更新失败: {e}")

                            with col_cancel:
                                if st.form_submit_button("取消"):
                                    st.session_state[f"editing_{pos['id']}"] = False
                                    st.rerun()

                    st.divider()

    else:
        st.info("暂无持仓，点击上方添加新持仓")

except Exception as e:
    st.error(f"获取持仓列表失败: {e}")

# ============ 持仓分析 ============
st.divider()
st.header("持仓分析")

try:
    summary = client.get_positions_summary()

    if summary and "positions" in summary and len(summary["positions"]) > 0:
        positions = summary["positions"]

        # 盈亏排行
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("盈利排行")
            profit_positions = sorted(
                [p for p in positions if p.get('pnl_cny', 0) > 0],
                key=lambda x: x.get('pnl_cny', 0),
                reverse=True
            )[:5]

            if profit_positions:
                for i, p in enumerate(profit_positions, 1):
                    pnl = p.get('pnl_cny', 0)
                    pnl_pct = p.get('pnl_percent', 0)
                    st.write(f"{i}. **{p.get('name', p.get('symbol'))}** - "
                            f"<span style='color:red'>+¥{pnl:,.2f} ({pnl_pct:+.2f}%)</span>",
                            unsafe_allow_html=True)
            else:
                st.info("暂无盈利持仓")

        with col2:
            st.subheader("亏损排行")
            loss_positions = sorted(
                [p for p in positions if p.get('pnl_cny', 0) < 0],
                key=lambda x: x.get('pnl_cny', 0)
            )[:5]

            if loss_positions:
                for i, p in enumerate(loss_positions, 1):
                    pnl = p.get('pnl_cny', 0)
                    pnl_pct = p.get('pnl_percent', 0)
                    st.write(f"{i}. **{p.get('name', p.get('symbol'))}** - "
                            f"<span style='color:green'>{pnl:,.2f} ({pnl_pct:+.2f}%)</span>",
                            unsafe_allow_html=True)
            else:
                st.info("暂无亏损持仓")

        # 持仓市值分布条形图
        st.subheader("持仓市值分布")

        df = pd.DataFrame(positions)
        if not df.empty and 'current_price' in df.columns:
            df['market_value'] = df.apply(
                lambda x: x.get('current_price', 0) * x.get('quantity', 0),
                axis=1
            )
            df = df.sort_values('market_value', ascending=True)

            fig = go.Figure(go.Bar(
                x=df['market_value'],
                y=df.apply(lambda x: f"{x.get('name', x.get('symbol'))} ({x.get('market')})", axis=1),
                orientation='h',
                marker_color=df['pnl_percent'].apply(
                    lambda x: 'red' if x > 0 else ('green' if x < 0 else 'gray')
                )
            ))

            fig.update_layout(
                title="持仓市值分布",
                xaxis_title="市值",
                yaxis_title="",
                height=max(300, len(df) * 40)
            )

            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.warning(f"获取持仓分析失败: {e}")

# 页脚
st.divider()
st.caption(f"数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
