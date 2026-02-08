"""交易录入页面 - 录入投资交易、查看交易历史、管理持仓"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from streamlit_app.api_client import EquilibraAPIClient

st.set_page_config(page_title="交易录入 - Equilibra", page_icon="📝", layout="wide")

# 初始化 API 客户端
@st.cache_resource
def get_api_client():
    return EquilibraAPIClient()

client = get_api_client()

st.title("📝 交易录入")
st.markdown("录入投资交易记录，自动计算持仓和成本")

# 资产类型和市场映射
ASSET_TYPES = {
    "stock": "股票",
    "fund": "基金",
    "bond": "债券",
    "bank_product": "银行理财",
    "crypto": "加密货币",
}

ASSET_TYPE_REVERSE = {v: k for k, v in ASSET_TYPES.items()}

MARKETS = {
    "stock": ["A股", "港股", "美股"],
    "fund": ["公募基金", "私募基金"],
    "bond": ["国债", "企业债", "可转债"],
    "bank_product": ["银行理财"],
    "crypto": ["OKX", "Binance", "其他"],
}

TRANSACTION_TYPES = {
    "buy": "买入",
    "sell": "卖出",
    "dividend": "分红",
    "interest": "利息",
    "transfer_in": "转入",
    "transfer_out": "转出",
}

TRANSACTION_TYPE_REVERSE = {v: k for k, v in TRANSACTION_TYPES.items()}

CURRENCIES = ["CNY", "HKD", "USD", "USDT"]

# ============ 录入交易 ============
st.header("录入交易")

with st.form("transaction_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)

    with col1:
        asset_type_display = st.selectbox(
            "资产类型",
            options=list(ASSET_TYPES.values()),
            index=0,
        )
        asset_type = ASSET_TYPE_REVERSE[asset_type_display]

        # 根据资产类型显示对应市场
        market_options = MARKETS.get(asset_type, ["其他"])
        market = st.selectbox("市场", options=market_options)

        symbol = st.text_input("代码", placeholder="如: 600000, BTC, 000001")

    with col2:
        name = st.text_input("名称", placeholder="如: 浦发银行, 比特币")

        tx_type_display = st.selectbox(
            "交易类型",
            options=list(TRANSACTION_TYPES.values()),
            index=0,
        )
        transaction_type = TRANSACTION_TYPE_REVERSE[tx_type_display]

        transaction_date = st.date_input("交易日期", value=date.today())

    with col3:
        quantity = st.number_input("数量", min_value=0.0, step=1.0, format="%.4f")
        price = st.number_input("单价", min_value=0.0, step=0.01, format="%.4f")
        fees = st.number_input("手续费", min_value=0.0, value=0.0, step=0.01)

    col4, col5 = st.columns(2)

    with col4:
        currency = st.selectbox("货币", options=CURRENCIES, index=0)
        account_name = st.text_input("账户名称", value="默认账户")

    with col5:
        notes = st.text_area("备注", placeholder="可选备注信息", height=100)

    # 显示计算的总金额
    if quantity > 0 and price > 0:
        total_amount = quantity * price
        st.info(f"💰 交易金额: {currency} {total_amount:,.2f} (不含手续费)")

    submitted = st.form_submit_button("📥 录入交易", use_container_width=True)

    if submitted:
        if not symbol:
            st.error("请输入代码")
        elif quantity <= 0:
            st.error("数量必须大于 0")
        elif price < 0:
            st.error("单价不能为负")
        else:
            try:
                # 转换日期为 ISO 格式
                tx_date_str = datetime.combine(transaction_date, datetime.min.time()).isoformat()

                result = client.create_transaction(
                    asset_type=asset_type,
                    symbol=symbol.upper(),
                    transaction_type=transaction_type,
                    quantity=quantity,
                    price=price,
                    transaction_date=tx_date_str,
                    name=name if name else None,
                    market=market,
                    fees=fees,
                    currency=currency,
                    account_name=account_name,
                    notes=notes if notes else None,
                )
                st.success(f"✅ 交易录入成功! ID: {result.get('id')}")
                st.rerun()
            except Exception as e:
                st.error(f"录入失败: {e}")

st.divider()

# ============ 交易记录列表 ============
st.header("交易记录")

# 筛选条件
col1, col2, col3, col4 = st.columns(4)

with col1:
    filter_asset_type = st.selectbox(
        "筛选资产类型",
        options=["全部"] + list(ASSET_TYPES.values()),
        key="filter_asset_type",
    )

with col2:
    filter_tx_type = st.selectbox(
        "筛选交易类型",
        options=["全部"] + list(TRANSACTION_TYPES.values()),
        key="filter_tx_type",
    )

with col3:
    filter_symbol = st.text_input("筛选代码", key="filter_symbol")

with col4:
    filter_limit = st.number_input("显示条数", min_value=10, max_value=500, value=50, step=10)

# 获取交易记录
try:
    # 构建筛选参数
    params = {"limit": filter_limit}
    if filter_asset_type != "全部":
        params["asset_type"] = ASSET_TYPE_REVERSE[filter_asset_type]
    if filter_tx_type != "全部":
        params["transaction_type"] = TRANSACTION_TYPE_REVERSE[filter_tx_type]
    if filter_symbol:
        params["symbol"] = filter_symbol.upper()

    transactions = client.get_transactions(**params)

    if transactions:
        # 转换为 DataFrame
        df_data = []
        for tx in transactions:
            df_data.append({
                "ID": tx["id"],
                "日期": tx["transaction_date"][:10] if tx["transaction_date"] else "",
                "类型": ASSET_TYPES.get(tx["asset_type"], tx["asset_type"]),
                "市场": tx.get("market", ""),
                "代码": tx["symbol"],
                "名称": tx.get("name", ""),
                "交易": TRANSACTION_TYPES.get(tx["transaction_type"], tx["transaction_type"]),
                "数量": tx["quantity"],
                "单价": tx["price"],
                "金额": tx["amount"],
                "手续费": tx.get("fees", 0),
                "货币": tx.get("currency", "CNY"),
                "账户": tx.get("account_name", ""),
            })

        df = pd.DataFrame(df_data)

        # 显示统计
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("交易笔数", len(df))
        with col2:
            buy_amount = df[df["交易"] == "买入"]["金额"].sum()
            st.metric("买入总额", f"¥{buy_amount:,.2f}")
        with col3:
            sell_amount = df[df["交易"] == "卖出"]["金额"].sum()
            st.metric("卖出总额", f"¥{sell_amount:,.2f}")
        with col4:
            total_fees = df["手续费"].sum()
            st.metric("总手续费", f"¥{total_fees:,.2f}")

        # 显示表格
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn("ID", width="small"),
                "数量": st.column_config.NumberColumn("数量", format="%.4f"),
                "单价": st.column_config.NumberColumn("单价", format="%.4f"),
                "金额": st.column_config.NumberColumn("金额", format="%.2f"),
                "手续费": st.column_config.NumberColumn("手续费", format="%.2f"),
            },
        )

        # 删除交易
        with st.expander("删除交易记录"):
            delete_id = st.number_input("输入要删除的交易 ID", min_value=1, step=1, key="delete_id")
            if st.button("🗑️ 删除", key="delete_btn"):
                try:
                    client.delete_transaction(int(delete_id))
                    st.success(f"已删除交易 ID: {delete_id}")
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败: {e}")
    else:
        st.info("暂无交易记录，请先录入交易")

except Exception as e:
    st.warning(f"获取交易记录失败: {e}")
    st.info("请确保后端服务已启动")

st.divider()

# ============ 持仓汇总 ============
st.header("持仓汇总")

try:
    holdings = client.get_investment_holdings()

    if holdings:
        # 转换为 DataFrame
        holdings_data = []
        for h in holdings:
            holdings_data.append({
                "类型": ASSET_TYPES.get(h["asset_type"], h["asset_type"]),
                "市场": h.get("market", ""),
                "代码": h["symbol"],
                "名称": h.get("name", ""),
                "数量": h["quantity"],
                "平均成本": h["avg_cost"],
                "总成本": h["total_cost"],
                "货币": h.get("currency", "CNY"),
                "账户": h.get("account_name", ""),
                "首次买入": h.get("first_buy_date", "")[:10] if h.get("first_buy_date") else "",
            })

        df_holdings = pd.DataFrame(holdings_data)

        # 汇总统计
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("持仓数量", f"{len(df_holdings)} 个")
        with col2:
            total_cost = df_holdings["总成本"].sum()
            st.metric("总成本", f"¥{total_cost:,.2f}")
        with col3:
            # 按类型统计
            type_counts = df_holdings["类型"].value_counts().to_dict()
            type_str = ", ".join([f"{k}: {v}" for k, v in type_counts.items()])
            st.metric("类型分布", type_str)

        st.dataframe(
            df_holdings,
            use_container_width=True,
            hide_index=True,
            column_config={
                "数量": st.column_config.NumberColumn("数量", format="%.4f"),
                "平均成本": st.column_config.NumberColumn("平均成本", format="%.4f"),
                "总成本": st.column_config.NumberColumn("总成本", format="%.2f"),
            },
        )

        # 查看单个资产的交易历史
        with st.expander("查看资产交易历史"):
            selected_symbol = st.selectbox(
                "选择资产",
                options=[h["symbol"] for h in holdings],
                key="history_symbol",
            )
            if st.button("查看历史", key="view_history_btn"):
                try:
                    history = client.get_holding_history(selected_symbol)
                    if history:
                        history_data = []
                        for tx in history:
                            history_data.append({
                                "日期": tx["transaction_date"][:10] if tx["transaction_date"] else "",
                                "交易": TRANSACTION_TYPES.get(tx["transaction_type"], tx["transaction_type"]),
                                "数量": tx["quantity"],
                                "单价": tx["price"],
                                "金额": tx["amount"],
                                "手续费": tx.get("fees", 0),
                            })
                        st.dataframe(pd.DataFrame(history_data), use_container_width=True, hide_index=True)
                    else:
                        st.info("暂无交易历史")
                except Exception as e:
                    st.error(f"获取历史失败: {e}")
    else:
        st.info("暂无持仓数据")

except Exception as e:
    st.warning(f"获取持仓汇总失败: {e}")

st.divider()

# ============ 基金/理财产品管理 ============
st.header("基金/理财产品")

tab1, tab2 = st.tabs(["产品列表", "添加产品"])

with tab1:
    try:
        products = client.get_fund_products()
        if products:
            products_data = []
            for p in products:
                products_data.append({
                    "类型": {"fund": "基金", "bond": "债券", "bank_product": "银行理财"}.get(p["product_type"], p["product_type"]),
                    "代码": p["symbol"],
                    "名称": p["name"],
                    "发行机构": p.get("issuer", ""),
                    "风险等级": p.get("risk_level", ""),
                    "预期收益": f"{p.get('expected_return', 0) * 100:.2f}%" if p.get("expected_return") else "",
                    "最新净值": p.get("nav", ""),
                    "净值日期": p.get("nav_date", "")[:10] if p.get("nav_date") else "",
                })
            st.dataframe(pd.DataFrame(products_data), use_container_width=True, hide_index=True)

            # 更新净值
            with st.expander("更新产品净值"):
                update_symbol = st.selectbox("选择产品", options=[p["symbol"] for p in products], key="update_nav_symbol")
                new_nav = st.number_input("新净值", min_value=0.0, step=0.0001, format="%.4f", key="new_nav")
                if st.button("更新净值", key="update_nav_btn"):
                    try:
                        client.update_fund_nav(update_symbol, new_nav)
                        st.success(f"已更新 {update_symbol} 净值为 {new_nav}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"更新失败: {e}")
        else:
            st.info("暂无产品数据")
    except Exception as e:
        st.warning(f"获取产品列表失败: {e}")

with tab2:
    with st.form("fund_product_form"):
        col1, col2 = st.columns(2)

        with col1:
            product_type = st.selectbox(
                "产品类型",
                options=["fund", "bond", "bank_product"],
                format_func=lambda x: {"fund": "基金", "bond": "债券", "bank_product": "银行理财"}[x],
            )
            fund_symbol = st.text_input("产品代码", placeholder="如: 000001")
            fund_name = st.text_input("产品名称", placeholder="如: 华夏成长混合")
            fund_issuer = st.text_input("发行机构", placeholder="如: 华夏基金")

        with col2:
            risk_level = st.selectbox("风险等级", options=["R1", "R2", "R3", "R4", "R5", ""])
            expected_return = st.number_input("预期年化收益率", min_value=0.0, max_value=1.0, step=0.01, format="%.4f")
            fund_nav = st.number_input("当前净值", min_value=0.0, step=0.0001, format="%.4f")
            fund_currency = st.selectbox("货币", options=CURRENCIES, key="fund_currency")

        fund_submitted = st.form_submit_button("添加产品", use_container_width=True)

        if fund_submitted:
            if not fund_symbol or not fund_name:
                st.error("请输入产品代码和名称")
            else:
                try:
                    result = client.create_fund_product(
                        product_type=product_type,
                        symbol=fund_symbol,
                        name=fund_name,
                        issuer=fund_issuer if fund_issuer else None,
                        risk_level=risk_level if risk_level else None,
                        expected_return=expected_return if expected_return > 0 else None,
                        nav=fund_nav if fund_nav > 0 else None,
                        currency=fund_currency,
                    )
                    st.success(f"✅ 产品添加成功! ID: {result.get('id')}")
                    st.rerun()
                except Exception as e:
                    st.error(f"添加失败: {e}")
