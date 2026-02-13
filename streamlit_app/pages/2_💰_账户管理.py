"""
账户管理页面 - Phase 2.2
包含：账户列表、转账、持仓管理、市值同步
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import EquilibraAPIClient

st.set_page_config(page_title="账户管理", page_icon="💰", layout="wide")


@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return EquilibraAPIClient(base_url=api_url)


api_client = get_api_client()

st.title("💰 账户管理")
st.markdown("管理您的所有账户，支持现金账户、投资账户和持仓管理")
st.markdown("---")


def format_currency(amount, currency="CNY"):
    """格式化货币显示"""
    symbols = {"CNY": "¥", "USD": "$", "HKD": "HK$"}
    symbol = symbols.get(currency, currency)
    return f"{symbol}{float(amount or 0):,.2f}"


def _f(val):
    """Safely convert API value (may be string/None) to float."""
    return float(val or 0)


def load_accounts():
    """加载所有账户"""
    try:
        return api_client.get_accounts()
    except Exception as e:
        st.error(f"加载账户失败: {e}")
        return []


def load_holdings(account_id=None):
    """加载持仓"""
    try:
        return api_client.get_holdings(account_id)
    except Exception as e:
        st.error(f"加载持仓失败: {e}")
        return []


def create_transfer(from_id, to_id, amount, notes=None):
    """创建转账"""
    try:
        return api_client.create_transfer(from_id, to_id, amount, notes)
    except Exception as e:
        st.error(f"转账失败: {e}")
        return None


def create_holding(data):
    """添加持仓"""
    try:
        return api_client.create_holding(**data)
    except Exception as e:
        st.error(f"添加持仓失败: {e}")
        return None


def delete_holding(holding_id):
    """删除持仓"""
    try:
        return api_client.delete_holding(holding_id)
    except Exception as e:
        st.error(f"删除持仓失败: {e}")
        return None


def sync_holdings():
    """同步市值"""
    try:
        return api_client.sync_holdings_value()
    except Exception as e:
        st.error(f"同步失败: {e}")
        return None


# ============ 侧边栏 ============
with st.sidebar:
    st.header("💰 账户管理")

    if st.button("🔄 刷新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    st.subheader("快捷操作")
    if st.button("➕ 创建账户", use_container_width=True):
        st.session_state["show_create_account"] = True

    if st.button("💸 转账", use_container_width=True):
        st.session_state["show_transfer"] = True

    if st.button("➕ 添加持仓", use_container_width=True):
        st.session_state["show_add_holding"] = True

    if st.button("🔃 同步市值", use_container_width=True):
        with st.spinner("同步中..."):
            result = sync_holdings()
            if result:
                st.success(f"同步完成：{result.get('synced_count', 0)} 个持仓")
                st.cache_data.clear()

    if st.button("➕ 添加负债", use_container_width=True):
        st.session_state["show_create_liability"] = True


# ============ 创建账户对话框 ============
if "show_create_account" not in st.session_state:
    st.session_state["show_create_account"] = False

if st.session_state["show_create_account"]:
    with st.form("create_account_form"):
        st.subheader("➕ 创建账户")

        acc_name = st.text_input("账户名称", placeholder="如: 招商银行储蓄卡")
        acc_type = st.selectbox(
            "账户类型",
            options=["cash", "investment"],
            format_func=lambda x: "现金账户" if x == "cash" else "投资账户",
        )

        col1, col2 = st.columns(2)
        with col1:
            acc_institution = st.text_input("机构（可选）", placeholder="如: 招商银行")
        with col2:
            acc_currency = st.selectbox("币种", options=["CNY", "USD", "HKD"])

        acc_initial_balance = st.number_input("初始余额", min_value=0.0, step=100.0, value=0.0)

        col1, col2 = st.columns(2)
        with col1:
            acc_submitted = st.form_submit_button("创建", type="primary")
        with col2:
            if st.form_submit_button("取消"):
                st.session_state["show_create_account"] = False
                st.rerun()

        if acc_submitted:
            if not acc_name or not acc_name.strip():
                st.error("账户名称不能为空")
            elif acc_initial_balance < 0:
                st.error("初始余额不能为负数")
            else:
                try:
                    result = api_client.create_account(
                        name=acc_name.strip(),
                        account_type=acc_type,
                        institution=acc_institution if acc_institution else None,
                        initial_balance=acc_initial_balance,
                        currency=acc_currency,
                    )
                    if result:
                        st.success("账户创建成功！")
                        st.session_state["show_create_account"] = False
                        st.cache_data.clear()
                        st.rerun()
                except Exception as e:
                    st.error(f"创建账户失败: {e}")

    st.markdown("---")


# ============ 转账对话框 ============
if "show_transfer" not in st.session_state:
    st.session_state["show_transfer"] = False

if st.session_state["show_transfer"]:
    with st.form("transfer_form"):
        st.subheader("💸 转账")

        accounts = load_accounts()
        account_options = [
            (a["id"], a["name"], a["account_type"], a["balance"], a.get("currency", "CNY"))
            for a in accounts
        ]

        from_account_id = st.selectbox(
            "转出账户",
            options=account_options,
            format_func=lambda x: f"{x[1]} ({format_currency(x[3], x[4])}) - {x[2]}",
        )

        to_account_id = st.selectbox(
            "转入账户",
            options=account_options,
            format_func=lambda x: f"{x[1]} ({format_currency(x[3], x[4])}) - {x[2]}",
        )

        amount = st.number_input("转账金额", min_value=0.01, step=100.0)
        notes = st.text_input("备注")

        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("确认转账", type="primary")
        with col2:
            if st.form_submit_button("取消"):
                st.session_state["show_transfer"] = False
                st.rerun()

        if submitted:
            if from_account_id[0] == to_account_id[0]:
                st.error("不能向同一账户转账")
            elif amount <= 0:
                st.error("转账金额必须大于0")
            elif _f(from_account_id[3]) < amount:
                st.error("账户余额不足")
            else:
                result = create_transfer(from_account_id[0], to_account_id[0], amount, notes)
                if result:
                    st.success(f"转账成功！")
                    st.session_state["show_transfer"] = False
                    st.cache_data.clear()
                    st.rerun()

    st.markdown("---")


# ============ 添加持仓对话框 ============
if "show_add_holding" not in st.session_state:
    st.session_state["show_add_holding"] = False

if st.session_state["show_add_holding"]:
    with st.form("holding_form"):
        st.subheader("➕ 添加持仓")

        accounts = load_accounts()
        investment_accounts = [a for a in accounts if a["account_type"] == "investment"]

        if not investment_accounts:
            st.error("没有投资账户，请先创建投资账户")
            selected_id = None
        else:
            account_options = {a["name"]: a["id"] for a in investment_accounts}
            selected_name = st.selectbox(
                "所属账户",
                options=list(account_options.keys()),
            )
            selected_id = account_options[selected_name] if selected_name else None

            symbol = st.text_input("代码", placeholder="如: YEB, 00700.HK")
            name = st.text_input("名称", placeholder="如: 余额宝, 腾讯控股")

            asset_type = st.selectbox(
                "资产类型",
                options=["stock", "fund", "bond", "crypto", "money_market"],
                format_func=lambda x: {
                    "stock": "股票",
                    "fund": "基金",
                    "bond": "债券",
                    "crypto": "加密货币",
                    "money_market": "货币基金",
                }.get(x, x),
            )

            is_liquid = st.checkbox("高流动性资产（如余额宝）", value=False)
            st.caption("勾选后计入可用现金，如余额宝等T+0资产")

            col1, col2 = st.columns(2)
            with col1:
                quantity = st.number_input("数量", min_value=0.0, step=1.0)
            with col2:
                avg_cost = st.number_input("成本价", min_value=0.0, step=0.01)

            col3, col4 = st.columns(2)
            with col3:
                current_price = st.number_input("当前价格", min_value=0.0, step=0.01)
            with col4:
                current_value = st.number_input("当前市值", min_value=0.0, step=100.0)

            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("添加", type="primary")
            with col2:
                if st.form_submit_button("取消"):
                    st.session_state["show_add_holding"] = False
                    st.rerun()

            if submitted:
                if not symbol or not name:
                    st.error("请填写代码和名称")
                elif quantity <= 0:
                    st.error("数量必须大于0")
                elif not selected_id:
                    st.error("请选择账户")
                else:
                    result = create_holding(
                        {
                            "account_id": selected_id,
                            "symbol": symbol,
                            "name": name,
                            "asset_type": asset_type,
                            "quantity": quantity,
                            "avg_cost": avg_cost,
                            "current_price": current_price if current_price > 0 else None,
                            "current_value": current_value if current_value > 0 else None,
                            "is_liquid": is_liquid,
                        }
                    )
                    if result:
                        st.success("持仓添加成功！")
                        st.session_state["show_add_holding"] = False
                        st.cache_data.clear()
                        st.rerun()

    st.markdown("---")


# ============ 创建负债对话框 ============
if "show_create_liability" not in st.session_state:
    st.session_state["show_create_liability"] = False

if st.session_state["show_create_liability"]:
    with st.form("create_liability_form"):
        st.subheader("➕ 添加负债")

        liab_name = st.text_input("负债名称", placeholder="如: 房贷")
        liab_type = st.selectbox(
            "负债类型",
            options=["mortgage", "car_loan", "credit_card", "other"],
            format_func=lambda x: {"mortgage": "房贷", "car_loan": "车贷", "credit_card": "信用卡", "other": "其他"}.get(x, x),
        )

        col1, col2 = st.columns(2)
        with col1:
            liab_institution = st.text_input("机构（可选）", placeholder="如: 工商银行")
        with col2:
            liab_original_amount = st.number_input("原始金额", min_value=0.0, step=1000.0)

        col3, col4 = st.columns(2)
        with col3:
            liab_remaining_amount = st.number_input("剩余金额", min_value=0.0, step=1000.0)
        with col4:
            liab_monthly_payment = st.number_input("月供（可选）", min_value=0.0, step=100.0)

        col5, col6 = st.columns(2)
        with col5:
            liab_interest_rate = st.number_input("年利率%（可选）", min_value=0.0, max_value=100.0, step=0.1)
        with col6:
            liab_payment_day = st.number_input("还款日（可选）", min_value=0, max_value=31, step=1)

        col7, col8 = st.columns(2)
        with col7:
            liab_start_date = st.date_input("开始日期（可选）")
        with col8:
            liab_end_date = st.date_input("结束日期（可选）")

        liab_notes = st.text_area("备注（可选）")

        col1, col2 = st.columns(2)
        with col1:
            liab_submitted = st.form_submit_button("创建", type="primary")
        with col2:
            if st.form_submit_button("取消"):
                st.session_state["show_create_liability"] = False
                st.rerun()

        if liab_submitted:
            if not liab_name or not liab_name.strip():
                st.error("负债名称不能为空")
            elif liab_original_amount <= 0:
                st.error("原始金额必须大于0")
            elif liab_remaining_amount < 0:
                st.error("剩余金额不能为负数")
            else:
                try:
                    result = api_client.create_liability(
                        name=liab_name.strip(),
                        liability_type=liab_type,
                        original_amount=liab_original_amount,
                        remaining_amount=liab_remaining_amount,
                        institution=liab_institution if liab_institution else None,
                        monthly_payment=liab_monthly_payment if liab_monthly_payment > 0 else None,
                        interest_rate=liab_interest_rate if liab_interest_rate > 0 else None,
                        start_date=str(liab_start_date) if liab_start_date else None,
                        end_date=str(liab_end_date) if liab_end_date else None,
                        payment_day=liab_payment_day if liab_payment_day > 0 else None,
                        notes=liab_notes if liab_notes else None,
                    )
                    if result:
                        st.success("负债创建成功！")
                        st.session_state["show_create_liability"] = False
                        st.cache_data.clear()
                        st.rerun()
                except Exception as e:
                    st.error(f"创建负债失败: {e}")

    st.markdown("---")


# ============ 还款对话框 ============
if "show_payment_form" not in st.session_state:
    st.session_state["show_payment_form"] = None

if st.session_state["show_payment_form"]:
    liability_id = st.session_state["show_payment_form"]
    with st.form("payment_form"):
        st.subheader("记录还款")

        payment_amount = st.number_input("还款金额", min_value=0.01, step=100.0)
        payment_date = st.date_input("还款日期", value=datetime.now())

        accounts = load_accounts()
        account_options = [(None, "不关联账户")] + [(a["id"], a["name"]) for a in accounts]
        payment_account = st.selectbox(
            "还款账户（可选）",
            options=account_options,
            format_func=lambda x: x[1],
        )

        col1, col2 = st.columns(2)
        with col1:
            payment_principal = st.number_input("本金（可选）", min_value=0.0, step=100.0)
        with col2:
            payment_interest = st.number_input("利息（可选）", min_value=0.0, step=10.0)

        payment_notes = st.text_input("备注（可选）")

        col1, col2 = st.columns(2)
        with col1:
            payment_submitted = st.form_submit_button("确认还款", type="primary")
        with col2:
            if st.form_submit_button("取消"):
                st.session_state["show_payment_form"] = None
                st.rerun()

        if payment_submitted:
            if payment_amount <= 0:
                st.error("还款金额必须大于0")
            else:
                try:
                    result = api_client.create_liability_payment(
                        liability_id=liability_id,
                        amount=payment_amount,
                        payment_date=str(payment_date),
                        account_id=payment_account[0] if payment_account[0] else None,
                        principal=payment_principal if payment_principal > 0 else None,
                        interest=payment_interest if payment_interest > 0 else None,
                        notes=payment_notes if payment_notes else None,
                    )
                    if result:
                        st.success("还款记录成功！")
                        st.session_state["show_payment_form"] = None
                        st.cache_data.clear()
                        st.rerun()
                except Exception as e:
                    st.error(f"记录还款失败: {e}")

    st.markdown("---")


# ============ 加载数据 ============
accounts = load_accounts()
holdings = load_holdings()

try:
    liabilities = api_client.get_liabilities(is_active=True)
except Exception as e:
    st.error(f"加载负债失败: {e}")
    liabilities = []

cash_accounts = [a for a in accounts if a["account_type"] == "cash"]
investment_accounts = [a for a in accounts if a["account_type"] == "investment"]


# ============ 现金账户区域 ============
st.subheader("🏦 现金账户")

if cash_accounts:
    for account in cash_accounts:
        with st.expander(f"💵 {account['name']}", expanded=False):
            col1, col2, col3, col4 = st.columns(4)

            currency = account.get("currency", "CNY")
            balance = account.get("balance", 0)
            total_value = account.get("total_value", balance)

            with col1:
                st.metric("余额", format_currency(balance, currency))
            with col2:
                st.metric("总资产", format_currency(total_value, currency))
            with col3:
                institution = account.get("institution", "")
                st.text(f"机构: {institution}")
            with col4:
                account_number = account.get("account_number", "")
                st.text(f"账号: {account_number}")

            if st.button("🗑️ 删除账户", key=f"del_acc_{account['id']}"):
                try:
                    api_client.delete_account(account["id"])
                    st.success("账户已删除")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败: {e}")
else:
    st.info("暂无现金账户")


# ============ 投资账户区域 ============
st.subheader("📈 投资账户")

if investment_accounts:
    for account in investment_accounts:
        account_holdings = [h for h in holdings if h.get("account_id") == account["id"]]

        currency = account.get("currency", "CNY")
        balance = account.get("balance", 0)
        available_cash = account.get("available_cash", balance)
        holdings_value = account.get("holdings_value", 0)
        total_value = account.get("total_value", balance)

        with st.expander(f"📊 {account['name']}", expanded=True):
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("总资产", format_currency(total_value, currency))
            with col2:
                st.metric("可用现金", format_currency(available_cash, currency))
            with col3:
                st.metric("持仓市值", format_currency(holdings_value, currency))
            with col4:
                institution = account.get("institution", "")
                st.text(f"机构: {institution}")

            # 持仓明细
            if account_holdings:
                st.markdown("**持仓明细**")

                for holding in account_holdings:
                    h_col1, h_col2, h_col3, h_col4 = st.columns([2, 1, 1, 1])

                    with h_col1:
                        liquid_icon = "💧" if holding.get("is_liquid") else "📈"
                        st.write(f"{liquid_icon} **{holding['name']}** ({holding['symbol']})")
                        asset_type_display = {
                            "stock": "股票",
                            "fund": "基金",
                            "bond": "债券",
                            "crypto": "加密货币",
                            "money_market": "货币基金",
                        }.get(holding.get("asset_type", ""), holding.get("asset_type", ""))
                        st.caption(f"类型: {asset_type_display}")

                    with h_col2:
                        qty = holding.get("quantity", 0)
                        price = holding.get("current_price", 0)
                        st.write(f"数量: {float(qty or 0):,.2f}")
                        st.caption(f"单价: {format_currency(price, currency)}")

                    with h_col3:
                        value = holding.get("current_value", 0)
                        st.write(f"市值: {format_currency(value, currency)}")

                    with h_col4:
                        if st.button("删除", key=f"delete_{holding['id']}"):
                            if delete_holding(holding["id"]):
                                st.success("删除成功")
                                st.cache_data.clear()
                                st.rerun()
            else:
                st.info("暂无持仓")

            # 删除账户按钮
            if account_holdings:
                st.warning("⚠️ 该账户有持仓，删除将同时清除所有持仓记录")
            if st.button("🗑️ 删除账户", key=f"del_acc_{account['id']}"):
                try:
                    api_client.delete_account(account["id"])
                    st.success("账户已删除")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败: {e}")
else:
    st.info("暂无投资账户")


# ============ 负债账户区域 ============
st.subheader("🏦 负债账户")

if liabilities:
    for liability in liabilities:
        liability_type_display = {
            "mortgage": "房贷",
            "car_loan": "车贷",
            "credit_card": "信用卡",
            "other": "其他",
        }.get(liability.get("liability_type", ""), liability.get("liability_type", ""))

        with st.expander(f"💳 {liability['name']} ({liability_type_display})", expanded=False):
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("剩余金额", format_currency(liability.get("remaining_amount", 0)))
            with col2:
                monthly_payment = liability.get("monthly_payment", 0)
                st.metric("月供", format_currency(monthly_payment) if monthly_payment else "未设置")
            with col3:
                institution = liability.get("institution", "")
                st.text(f"机构: {institution if institution else '未设置'}")
            with col4:
                st.text(f"类型: {liability_type_display}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("记录还款", key=f"pay_liab_{liability['id']}"):
                    st.session_state["show_payment_form"] = liability["id"]
                    st.rerun()
            with col2:
                if st.button("删除", key=f"del_liab_{liability['id']}"):
                    try:
                        api_client.delete_liability(liability["id"])
                        st.success("负债已删除")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"删除失败: {e}")
else:
    st.info("暂无负债账户")


# ============ 账户统计 ============
st.markdown("---")
st.subheader("📊 账户统计")

if accounts or liabilities:
    total_assets = sum(_f(a.get("total_value", a.get("balance", 0))) for a in accounts)
    total_cash = sum(_f(a.get("balance", 0)) for a in cash_accounts)
    total_holdings = sum(_f(a.get("holdings_value", 0)) for a in investment_accounts)
    total_liabilities = sum(_f(l.get("remaining_amount", 0)) for l in liabilities)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总资产", format_currency(total_assets))
    with col2:
        st.metric("现金总额", format_currency(total_cash))
    with col3:
        st.metric("投资总额", format_currency(total_holdings))
    with col4:
        st.metric("负债总额", format_currency(total_liabilities))
