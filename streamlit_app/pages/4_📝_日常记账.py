"""
日常记账页面 - 表格化批量录入 + 历史管理
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import FolioAPIClient

st.set_page_config(page_title="日常记账", page_icon="📝", layout="wide")


@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return FolioAPIClient(base_url=api_url)


api_client = get_api_client()

st.title("📝 日常记账")
st.markdown("---")


def _f(val):
    return float(val or 0)


def format_currency(amount, currency="CNY"):
    symbols = {"CNY": "¥", "USD": "$", "HKD": "HK$"}
    symbol = symbols.get(currency, currency)
    return f"{symbol}{float(amount or 0):,.2f}"


# ============ Load data ============

@st.cache_data(ttl=30)
def load_accounts():
    try:
        return api_client.get_accounts()
    except Exception as e:
        st.error(f"加载账户失败: {e}")
        return []


@st.cache_data(ttl=60)
def load_categories():
    try:
        return api_client.get_categories()
    except Exception as e:
        st.error(f"加载分类失败: {e}")
        return []


@st.cache_data(ttl=30)
def load_budgets():
    try:
        return api_client.get_budgets(status="active")
    except Exception as e:
        st.error(f"加载预算失败: {e}")
        return []


accounts = load_accounts()
categories = load_categories()
budgets = load_budgets()

if not accounts:
    st.warning("请先在账户管理页面添加账户")
    st.stop()

# Build option maps
account_map = {a["name"]: a["id"] for a in accounts}
account_names = list(account_map.keys())

# Build category options: "大类 - 子类"
cat_options = []
cat_lookup = {}
for cat in categories:
    for sub in cat.get("subcategories", []):
        label = f"{cat['category']} - {sub}"
        cat_options.append(label)
        cat_lookup[label] = (cat["category"], sub)

if not cat_options:
    cat_options = ["其他 - 其他支出"]
    cat_lookup["其他 - 其他支出"] = ("其他", "其他支出")

budget_map = {"无": None}
for b in budgets:
    remaining = float(b.get("remaining") or 0)
    label = f"{b['name']} (剩余 ¥{remaining:,.0f})"
    budget_map[label] = b["id"]
budget_names = list(budget_map.keys())

payment_methods = ["支付宝", "微信支付", "现金", "银行卡", "信用卡", "其他"]

# ============ Sidebar ============
with st.sidebar:
    st.header("📝 日常记账")
    if accounts:
        total_balance = sum(_f(a.get("balance", 0)) for a in accounts)
        st.metric("账户总余额", format_currency(total_balance))

# ============ Batch entry ============
st.subheader("新增支出")

if "new_rows" not in st.session_state:
    st.session_state.new_rows = pd.DataFrame(
        [
            {
                "金额": 0.0,
                "账户": account_names[0],
                "分类": cat_options[0],
                "日期": date.today(),
                "商户": "",
                "支付方式": payment_methods[0],
                "预算": budget_names[0],
                "备注": "",
            }
        ]
    )

edited_df = st.data_editor(
    st.session_state.new_rows,
    column_config={
        "金额": st.column_config.NumberColumn("金额", min_value=0.01, step=1.0, format="%.2f"),
        "账户": st.column_config.SelectboxColumn("账户", options=account_names, required=True),
        "分类": st.column_config.SelectboxColumn("分类", options=cat_options, required=True),
        "日期": st.column_config.DateColumn("日期", default=date.today()),
        "商户": st.column_config.TextColumn("商户"),
        "支付方式": st.column_config.SelectboxColumn("支付方式", options=payment_methods),
        "预算": st.column_config.SelectboxColumn("预算", options=budget_names),
        "备注": st.column_config.TextColumn("备注"),
    },
    num_rows="dynamic",
    use_container_width=True,
    key="expense_editor",
)

col_submit, col_clear = st.columns([1, 1])
with col_submit:
    submit = st.button("批量提交", type="primary", use_container_width=True)
with col_clear:
    if st.button("清空", use_container_width=True):
        st.session_state.new_rows = pd.DataFrame(
            [
                {
                    "金额": 0.0,
                    "账户": account_names[0],
                    "分类": cat_options[0],
                    "日期": date.today(),
                    "商户": "",
                    "支付方式": payment_methods[0],
                    "预算": budget_names[0],
                    "备注": "",
                }
            ]
        )
        st.rerun()

if submit:
    valid_rows = edited_df[edited_df["金额"] > 0]
    if valid_rows.empty:
        st.warning("没有有效的支出记录（金额需大于0）")
    else:
        success_count = 0
        errors = []
        for _, row in valid_rows.iterrows():
            cat_key = row["分类"]
            category, subcategory = cat_lookup.get(cat_key, ("其他", None))
            account_id = account_map.get(row["账户"])
            budget_label = row.get("预算", "无")
            budget_id = budget_map.get(budget_label)

            expense_date = row["日期"]
            if isinstance(expense_date, datetime):
                expense_date = expense_date.date()

            data = {
                "account_id": account_id,
                "amount": float(row["金额"]),
                "expense_date": str(expense_date),
                "category": category,
                "subcategory": subcategory,
                "merchant": row["商户"] if row["商户"] else None,
                "payment_method": row["支付方式"] if row["支付方式"] else None,
                "notes": row["备注"] if row["备注"] else None,
            }
            if budget_id:
                data["budget_id"] = budget_id

            try:
                api_client.create_expense(**data)
                success_count += 1
            except Exception as e:
                errors.append(f"第{_ + 1}行: {e}")

        if success_count:
            st.success(f"成功提交 {success_count} 笔支出")
            st.cache_data.clear()
            # Reset the editor
            st.session_state.new_rows = pd.DataFrame(
                [
                    {
                        "金额": 0.0,
                        "账户": account_names[0],
                        "分类": cat_options[0],
                        "日期": date.today(),
                        "商户": "",
                        "支付方式": payment_methods[0],
                        "预算": budget_names[0],
                        "备注": "",
                    }
                ]
            )
            st.rerun()
        for err in errors:
            st.error(err)

# ============ History ============
st.markdown("---")
st.subheader("支出历史")

col_f1, col_f2 = st.columns(2)
with col_f1:
    start_date = st.date_input("开始日期", value=date.today() - timedelta(days=30), key="hist_start")
with col_f2:
    end_date = st.date_input("结束日期", value=date.today(), key="hist_end")

try:
    all_expenses = api_client.get_expenses()

    # Filter by date range
    filtered = []
    for e in all_expenses:
        try:
            exp_date = datetime.strptime(e.get("expense_date", ""), "%Y-%m-%d").date()
            if start_date <= exp_date <= end_date:
                filtered.append(e)
        except (ValueError, TypeError):
            continue

    if filtered:
        # Build account id->name map
        acc_id_name = {a["id"]: a["name"] for a in accounts}
        # Build budget id->name map
        budget_id_name = {b["id"]: b["name"] for b in budgets}

        history_data = []
        for e in filtered:
            cat_display = e.get("category", "")
            if e.get("subcategory"):
                cat_display += f" - {e['subcategory']}"
            history_data.append(
                {
                    "选择": False,
                    "ID": e["id"],
                    "日期": e.get("expense_date", ""),
                    "金额": float(e.get("amount", 0)),
                    "分类": cat_display,
                    "商户": e.get("merchant") or "",
                    "支付方式": e.get("payment_method") or "",
                    "账户": acc_id_name.get(e.get("account_id"), ""),
                    "预算": budget_id_name.get(e.get("budget_id"), "") if e.get("budget_id") else "",
                    "备注": e.get("notes") or "",
                }
            )

        hist_df = pd.DataFrame(history_data)

        edited_hist = st.data_editor(
            hist_df,
            column_config={
                "选择": st.column_config.CheckboxColumn("选择", default=False),
                "ID": st.column_config.NumberColumn("ID", disabled=True),
                "日期": st.column_config.TextColumn("日期", disabled=True),
                "金额": st.column_config.NumberColumn("金额", format="%.2f", disabled=True),
                "分类": st.column_config.TextColumn("分类", disabled=True),
                "商户": st.column_config.TextColumn("商户", disabled=True),
                "支付方式": st.column_config.TextColumn("支付方式", disabled=True),
                "账户": st.column_config.TextColumn("账户", disabled=True),
                "预算": st.column_config.TextColumn("预算", disabled=True),
                "备注": st.column_config.TextColumn("备注", disabled=True),
            },
            disabled=["ID", "日期", "金额", "分类", "商户", "支付方式", "账户", "预算", "备注"],
            hide_index=True,
            use_container_width=True,
            key="history_editor",
        )

        selected = edited_hist[edited_hist["选择"] == True]
        if not selected.empty:
            if st.button(f"删除选中的 {len(selected)} 笔记录", type="primary"):
                del_ok = 0
                del_err = []
                for _, row in selected.iterrows():
                    try:
                        api_client.delete_expense(int(row["ID"]))
                        del_ok += 1
                    except Exception as e:
                        del_err.append(f"ID {row['ID']}: {e}")
                if del_ok:
                    st.success(f"成功删除 {del_ok} 笔记录")
                    st.cache_data.clear()
                    st.rerun()
                for err in del_err:
                    st.error(err)

        st.caption(f"共 {len(filtered)} 笔记录，合计 {format_currency(sum(float(e.get('amount', 0)) for e in filtered))}")
    else:
        st.info("该日期范围内暂无支出记录")
except Exception as e:
    st.error(f"加载支出记录失败: {e}")
