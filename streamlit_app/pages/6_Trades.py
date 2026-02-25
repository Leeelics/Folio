"""
交易录入页面 - 投资交易买入/卖出/分红录入 + 历史管理
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import FolioAPIClient

st.set_page_config(page_title="交易录入", page_icon="📝", layout="wide")


@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return FolioAPIClient(base_url=api_url)


api_client = get_api_client()

st.title("📝 交易录入")
st.markdown("---")


def format_currency(amount, currency="CNY"):
    symbols = {"CNY": "¥", "USD": "$", "HKD": "HK$"}
    symbol = symbols.get(currency, currency)
    return f"{symbol}{float(amount or 0):,.2f}"


# ============ Constants ============

ASSET_TYPES = ["stock", "fund", "bond", "crypto", "other"]
ASSET_TYPE_LABELS = {
    "stock": "股票",
    "fund": "基金",
    "bond": "债券",
    "crypto": "加密货币",
    "other": "其他",
}

TRANSACTION_TYPES = ["buy", "sell", "dividend"]
TRANSACTION_TYPE_LABELS = {
    "buy": "买入",
    "sell": "卖出",
    "dividend": "分红",
}

MARKETS = ["A股", "港股", "美股", "其他"]
MARKET_CODES = {
    "A股": "CN",
    "港股": "HK",
    "美股": "US",
    "其他": None,
}

CURRENCIES = ["CNY", "USD", "HKD"]

# ============ Sidebar ============
with st.sidebar:
    st.header("📝 交易录入")
    st.caption("记录投资交易：买入、卖出、分红")

# ============ New Transaction Form ============
st.subheader("新增交易")

col1, col2, col3 = st.columns(3)
with col1:
    tx_type_label = st.selectbox(
        "交易类型",
        options=list(TRANSACTION_TYPE_LABELS.values()),
        key="tx_type",
    )
    tx_type = [k for k, v in TRANSACTION_TYPE_LABELS.items() if v == tx_type_label][0]
with col2:
    asset_type_label = st.selectbox(
        "资产类型",
        options=list(ASSET_TYPE_LABELS.values()),
        key="asset_type",
    )
    asset_type = [k for k, v in ASSET_TYPE_LABELS.items() if v == asset_type_label][0]
with col3:
    market_label = st.selectbox("市场", options=MARKETS, key="market")
    market = MARKET_CODES[market_label]

col4, col5 = st.columns(2)
with col4:
    symbol = st.text_input("代码", placeholder="例: 600519", key="symbol")
with col5:
    name = st.text_input("名称", placeholder="例: 贵州茅台", key="name")

col6, col7, col8 = st.columns(3)
with col6:
    quantity = st.number_input(
        "数量",
        min_value=0.0001,
        value=100.0,
        step=1.0,
        format="%.4f",
        key="quantity",
    )
with col7:
    if tx_type == "dividend":
        price = st.number_input(
            "每股分红",
            min_value=0.0001,
            value=1.0,
            step=0.01,
            format="%.4f",
            key="price",
        )
    else:
        price = st.number_input(
            "价格",
            min_value=0.0001,
            value=10.0,
            step=0.01,
            format="%.4f",
            key="price",
        )
with col8:
    fees = st.number_input(
        "手续费",
        min_value=0.0,
        value=0.0,
        step=0.01,
        format="%.2f",
        key="fees",
    )

col9, col10, col11 = st.columns(3)
with col9:
    tx_date = st.date_input("交易日期", value=date.today(), key="tx_date")
with col10:
    currency = st.selectbox("币种", options=CURRENCIES, key="currency")
with col11:
    account_name = st.text_input("账户名称", value="默认账户", key="account_name")

notes = st.text_input("备注", placeholder="可选", key="notes")

# Show transaction summary
total_amount = quantity * price
st.info(
    f"交易金额: {format_currency(total_amount, currency)} | "
    f"手续费: {format_currency(fees, currency)} | "
    f"合计: {format_currency(total_amount + fees, currency)}"
)

col_submit, col_clear = st.columns([1, 1])
with col_submit:
    submit = st.button("提交交易", type="primary", use_container_width=True)
with col_clear:
    if st.button("重置", use_container_width=True):
        st.rerun()

if submit:
    if not symbol.strip():
        st.warning("请输入资产代码")
    else:
        try:
            result = api_client.create_transaction(
                asset_type=asset_type,
                symbol=symbol.strip(),
                transaction_type=tx_type,
                quantity=quantity,
                price=price,
                transaction_date=str(tx_date),
                name=name.strip() if name.strip() else None,
                market=market,
                fees=fees,
                currency=currency,
                account_name=account_name.strip(),
                notes=notes.strip() if notes.strip() else None,
            )
            st.success(
                f"交易提交成功: {TRANSACTION_TYPE_LABELS[tx_type]} "
                f"{symbol} x {quantity} @ {format_currency(price, currency)}"
            )
            st.cache_data.clear()
        except Exception as e:
            st.error(f"提交失败: {e}")

# ============ Transaction History ============
st.markdown("---")
st.subheader("交易历史")

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    filter_type = st.selectbox(
        "筛选类型",
        options=["全部"] + list(TRANSACTION_TYPE_LABELS.values()),
        key="filter_type",
    )
with col_f2:
    hist_start = st.date_input(
        "开始日期", value=date.today() - timedelta(days=90), key="hist_start"
    )
with col_f3:
    hist_end = st.date_input("结束日期", value=date.today(), key="hist_end")

try:
    filter_tx_type = None
    if filter_type != "全部":
        filter_tx_type = [
            k for k, v in TRANSACTION_TYPE_LABELS.items() if v == filter_type
        ][0]

    all_transactions = api_client.get_transactions(
        transaction_type=filter_tx_type,
        start_date=str(hist_start),
        end_date=str(hist_end),
    )

    if all_transactions:
        history_data = []
        for t in all_transactions:
            tx_type_display = TRANSACTION_TYPE_LABELS.get(
                t.get("transaction_type", ""), t.get("transaction_type", "")
            )
            asset_type_display = ASSET_TYPE_LABELS.get(
                t.get("asset_type", ""), t.get("asset_type", "")
            )
            qty = float(t.get("quantity", 0))
            px = float(t.get("price", 0))
            fee = float(t.get("fees", 0))
            history_data.append(
                {
                    "选择": False,
                    "ID": t["id"],
                    "日期": t.get("transaction_date", ""),
                    "类型": tx_type_display,
                    "资产": asset_type_display,
                    "代码": t.get("symbol", ""),
                    "名称": t.get("name") or "",
                    "数量": qty,
                    "价格": px,
                    "金额": qty * px,
                    "手续费": fee,
                    "账户": t.get("account_name", ""),
                    "备注": t.get("notes") or "",
                }
            )

        hist_df = pd.DataFrame(history_data)

        edited_hist = st.data_editor(
            hist_df,
            column_config={
                "选择": st.column_config.CheckboxColumn("选择", default=False),
                "ID": st.column_config.NumberColumn("ID", disabled=True),
                "日期": st.column_config.TextColumn("日期", disabled=True),
                "类型": st.column_config.TextColumn("类型", disabled=True),
                "资产": st.column_config.TextColumn("资产", disabled=True),
                "代码": st.column_config.TextColumn("代码", disabled=True),
                "名称": st.column_config.TextColumn("名称", disabled=True),
                "数量": st.column_config.NumberColumn(
                    "数量", format="%.4f", disabled=True
                ),
                "价格": st.column_config.NumberColumn(
                    "价格", format="%.4f", disabled=True
                ),
                "金额": st.column_config.NumberColumn(
                    "金额", format="%.2f", disabled=True
                ),
                "手续费": st.column_config.NumberColumn(
                    "手续费", format="%.2f", disabled=True
                ),
                "账户": st.column_config.TextColumn("账户", disabled=True),
                "备注": st.column_config.TextColumn("备注", disabled=True),
            },
            disabled=[
                "ID", "日期", "类型", "资产", "代码", "名称",
                "数量", "价格", "金额", "手续费", "账户", "备注",
            ],
            hide_index=True,
            use_container_width=True,
            key="tx_history_editor",
        )

        selected = edited_hist[edited_hist["选择"] == True]
        if not selected.empty:
            if st.button(
                f"删除选中的 {len(selected)} 笔交易", type="primary"
            ):
                del_ok = 0
                del_err = []
                for _, row in selected.iterrows():
                    try:
                        api_client.delete_transaction(int(row["ID"]))
                        del_ok += 1
                    except Exception as e:
                        del_err.append(f"ID {row['ID']}: {e}")
                if del_ok:
                    st.success(f"成功删除 {del_ok} 笔交易")
                    st.cache_data.clear()
                    st.rerun()
                for err in del_err:
                    st.error(err)

        total_buy = sum(
            r["金额"]
            for _, r in hist_df.iterrows()
            if r["类型"] == "买入"
        )
        total_sell = sum(
            r["金额"]
            for _, r in hist_df.iterrows()
            if r["类型"] == "卖出"
        )
        total_div = sum(
            r["金额"]
            for _, r in hist_df.iterrows()
            if r["类型"] == "分红"
        )
        st.caption(
            f"共 {len(all_transactions)} 笔交易 | "
            f"买入: {format_currency(total_buy)} | "
            f"卖出: {format_currency(total_sell)} | "
            f"分红: {format_currency(total_div)}"
        )
    else:
        st.info("该日期范围内暂无交易记录")
except Exception as e:
    st.error(f"加载交易记录失败: {e}")
