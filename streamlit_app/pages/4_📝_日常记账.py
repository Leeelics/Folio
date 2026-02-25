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

# Build category options: separate main/sub lists
main_categories = []
sub_categories = []
cat_valid_pairs: dict[str, list[str]] = {}
for cat in categories:
    name = cat["category"]
    main_categories.append(name)
    subs = cat.get("subcategories", [])
    cat_valid_pairs[name] = subs
    sub_categories.extend(subs)

if not main_categories:
    main_categories = ["其他"]
    sub_categories = ["其他支出"]
    cat_valid_pairs["其他"] = ["其他支出"]

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

# ============ Category management ============
if "mgmt_expanded" not in st.session_state:
    st.session_state.mgmt_expanded = False

with st.expander("⚙️ 管理分类", expanded=st.session_state.mgmt_expanded):
    try:
        all_cats = api_client.get_all_categories()
    except Exception as e:
        st.error(f"加载分类失败: {e}")
        all_cats = []

    if all_cats:
        # --- Add new category ---
        st.markdown("**新增分类**")
        existing_mains = sorted(set(c["category"] for c in all_cats))
        main_options = existing_mains + ["➕ 新增大类"]
        col_m, col_s, col_btn = st.columns([2, 2, 1])
        with col_m:
            selected_main = st.selectbox("大类", main_options, key="mgmt_main")
            if selected_main == "➕ 新增大类":
                selected_main = st.text_input("新大类名称", key="mgmt_new_main")
        with col_s:
            new_sub = st.text_input("子类名称", key="mgmt_new_sub")
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("添加", key="mgmt_add"):
                if selected_main and new_sub:
                    try:
                        api_client.create_category(selected_main.strip(), new_sub.strip())
                        st.success(f"已添加: {selected_main} - {new_sub}")
                        st.cache_data.clear()
                        st.session_state.mgmt_expanded = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"添加失败: {e}")
                else:
                    st.warning("请填写大类和子类名称")

        # --- Toggle active status ---
        st.markdown("---")
        st.markdown("**现有分类**")
        # Group by main category
        grouped: dict[str, list] = {}
        for c in all_cats:
            grouped.setdefault(c["category"], []).append(c)

        for main_cat, items in grouped.items():
            st.markdown(f"**{main_cat}**")
            cat_df = pd.DataFrame([
                {"id": c["id"], "子分类": c["subcategory"], "启用": c["is_active"]}
                for c in items
            ])
            edited = st.data_editor(
                cat_df,
                column_config={
                    "id": st.column_config.NumberColumn("id", disabled=True),
                    "子分类": st.column_config.TextColumn("子分类", disabled=True),
                    "启用": st.column_config.CheckboxColumn("启用"),
                },
                hide_index=True,
                use_container_width=True,
                key=f"mgmt_{main_cat}",
            )
            # Detect changes
            changed = edited[edited["启用"] != cat_df["启用"]]
            if not changed.empty:
                if st.button(f"保存「{main_cat}」更改", key=f"mgmt_save_{main_cat}"):
                    for _, row in changed.iterrows():
                        try:
                            api_client.update_category(int(row["id"]), bool(row["启用"]))
                        except Exception as e:
                            st.error(f"更新失败: {e}")
                    st.success("已保存")
                    st.cache_data.clear()
                    st.session_state.mgmt_expanded = True
                    st.rerun()

# ============ Batch entry ============
st.subheader("新增支出")

if "new_rows" not in st.session_state:
    st.session_state.new_rows = pd.DataFrame(
        [
            {
                "金额": 0.0,
                "账户": account_names[0],
                "大类": main_categories[0],
                "子类": sub_categories[0],
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
        "大类": st.column_config.SelectboxColumn("大类", options=main_categories, required=True),
        "子类": st.column_config.SelectboxColumn("子类", options=sub_categories, required=True),
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
                    "大类": main_categories[0],
                    "子类": sub_categories[0],
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
            category = row["大类"]
            subcategory = row["子类"]
            if subcategory not in cat_valid_pairs.get(category, []):
                errors.append(f"第{_ + 1}行: 子类「{subcategory}」不属于大类「{category}」")
                continue
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
                        "大类": main_categories[0],
                        "子类": sub_categories[0],
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
            history_data.append(
                {
                    "选择": False,
                    "ID": e["id"],
                    "日期": e.get("expense_date", ""),
                    "金额": float(e.get("amount", 0)),
                    "大类": e.get("category", ""),
                    "子类": e.get("subcategory", ""),
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
                "大类": st.column_config.TextColumn("大类", disabled=True),
                "子类": st.column_config.TextColumn("子类", disabled=True),
                "商户": st.column_config.TextColumn("商户", disabled=True),
                "支付方式": st.column_config.TextColumn("支付方式", disabled=True),
                "账户": st.column_config.TextColumn("账户", disabled=True),
                "预算": st.column_config.TextColumn("预算", disabled=True),
                "备注": st.column_config.TextColumn("备注", disabled=True),
            },
            disabled=["ID", "日期", "金额", "大类", "子类", "商户", "支付方式", "账户", "预算", "备注"],
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
