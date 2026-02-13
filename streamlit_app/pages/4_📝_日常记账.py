"""
日常记账页面 - Phase 2.2
支持现金账户和投资账户（从balance扣减）
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import EquilibraAPIClient

st.set_page_config(page_title="日常记账", page_icon="📝", layout="wide")


@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return EquilibraAPIClient(base_url=api_url)


api_client = get_api_client()

st.title("📝 日常记账")
st.markdown("记录日常消费支出")
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


def load_categories():
    """加载支出分类"""
    try:
        return api_client.get_categories()
    except Exception as e:
        st.error(f"加载分类失败: {e}")
        return []


def load_budgets():
    """加载预算列表"""
    try:
        return api_client.get_budgets(status="active")
    except Exception as e:
        st.error(f"加载预算失败: {e}")
        return []


def create_expense(data):
    """创建支出"""
    try:
        return api_client.create_expense(**data)
    except Exception as e:
        st.error(f"创建支出失败: {e}")
        return None


# ============ 侧边栏 ============
with st.sidebar:
    st.header("📝 日常记账")
    st.info("💡 支持从现金账户和投资账户支出")
    
    st.divider()
    
    st.subheader("快捷信息")
    
    accounts = load_accounts()
    if accounts:
        total_balance = sum(_f(a.get("balance", 0)) for a in accounts)
        st.metric("账户总余额", format_currency(total_balance))


# 读取预选预算
budget_id_param = st.query_params.get("budget_id")

# ============ 主体表单 ============
with st.form("expense_form", clear_on_submit=False):
    st.subheader("💰 账户与金额")
    
    col1, col2 = st.columns(2)
    
    with col1:
        accounts = load_accounts()
        if not accounts:
            st.error("请先添加账户")
            st.stop()
        
        # 分组显示账户
        cash_accounts = [a for a in accounts if a["account_type"] == "cash"]
        investment_accounts = [a for a in accounts if a["account_type"] == "investment"]
        
        account_options = {}
        
        # 现金账户选项
        for acc in cash_accounts:
            balance = acc.get("balance", 0)
            currency = acc.get("currency", "CNY")
            label = f"💵 {acc['name']} ({format_currency(balance, currency)})"
            account_options[label] = acc["id"]
        
        # 投资账户选项
        for acc in investment_accounts:
            balance = acc.get("balance", 0)
            available_cash = acc.get("available_cash", balance)
            currency = acc.get("currency", "CNY")
            label = f"📈 {acc['name']} (可用: {format_currency(available_cash, currency)})"
            account_options[label] = acc["id"]
        
        selected_label = st.selectbox(
            "支付账户",
            options=list(account_options.keys()),
            help="选择支付账户。投资账户显示可用现金（含余额宝等高流动性资产），支出将从账户余额中扣减。",
        )
        account_id = account_options[selected_label]
        
        # 显示选中账户的详细信息
        selected_account = next((a for a in accounts if a["id"] == account_id), None)
        if selected_account:
            if selected_account["account_type"] == "investment":
                st.caption("💡 从投资账户支出将从余额扣减，不影响持仓。如需使用余额宝，请先转出到余额。")
    
    with col2:
        amount = st.number_input("支出金额", min_value=0.01, step=10.0)
    
    st.markdown("---")
    
    st.subheader("📅 日期与分类")
    
    col3, col4 = st.columns(2)
    
    with col3:
        expense_date = st.date_input("支出日期", value=date.today())
    
    with col4:
        categories = load_categories()
        if categories:
            category_options = {}
            for cat in categories:
                subcats = cat.get("subcategories", [])
                for sub in subcats:
                    label = f"{cat['category']} - {sub}"
                    category_options[label] = {
                        "category": cat["category"],
                        "subcategory": sub,
                    }
            
            selected_cat = st.selectbox(
                "支出分类",
                options=list(category_options.keys()),
            )
            category = category_options[selected_cat]["category"]
            subcategory = category_options[selected_cat]["subcategory"]
        else:
            category = "其他"
            subcategory = None
    
    st.markdown("---")
    
    st.subheader("📋 其他信息")
    
    col5, col6 = st.columns(2)
    
    with col5:
        merchant = st.text_input("商家/地点", placeholder="如: 麦当劳、星巴克")
    
    with col6:
        payment_method = st.selectbox(
            "支付方式",
            options=["现金", "支付宝", "微信支付", "银行卡", "信用卡", "其他"],
        )
    
    # 关联预算（可选）
    budgets = load_budgets()
    if budgets:
        budget_options = {f"{b['name']} (剩余: ¥{float(b['remaining'] or 0):,.0f})": b["id"] for b in budgets}
        
        # 预选预算
        default_index = 0
        if budget_id_param:
            for idx, (label, bid) in enumerate(budget_options.items(), start=1):
                if str(bid) == str(budget_id_param):
                    default_index = idx
                    break
        
        budget_label = st.selectbox(
            "关联预算（可选）",
            options=["不关联预算"] + list(budget_options.keys()),
            index=default_index,
        )
        if budget_label == "不关联预算":
            budget_id = None
        else:
            budget_id = budget_options[budget_label]
    else:
        budget_id = None
        st.caption("💡 暂无进行中的预算")
    
    is_shared = st.checkbox("共同开销", value=False)
    
    notes = st.text_area("备注", placeholder="添加其他说明...")
    
    submitted = st.form_submit_button("💾 记录支出", type="primary", use_container_width=True)


# ============ 提交处理 ============
if submitted:
    if amount <= 0:
        st.error("支出金额必须大于0")
    elif not selected_label:
        st.error("请选择支付账户")
    else:
        # 检查账户余额
        account = next((a for a in accounts if a["id"] == account_id), None)
        if account and _f(account["balance"]) < amount:
            if account["account_type"] == "investment":
                available = account.get("available_cash", 0)
                st.error(
                    f"账户余额不足！当前余额: {format_currency(account['balance'])}，"
                    f"可用现金: {format_currency(available)}。"
                    f"如需使用余额宝等高流动性资产，请先转出到余额。"
                )
            else:
                st.error(f"账户余额不足！当前余额: {format_currency(account['balance'])}")
        else:
            # 创建支出
            result = create_expense({
                "account_id": account_id,
                "budget_id": budget_id,
                "amount": amount,
                "expense_date": str(expense_date),
                "category": category,
                "subcategory": subcategory,
                "merchant": merchant if merchant else None,
                "payment_method": payment_method,
                "notes": notes if notes else None,
            })
            
            if result:
                st.success(f"✅ 支出记录成功！")
                
                # 显示详细信息
                with st.expander("查看详情", expanded=True):
                    st.write(f"**账户**: {selected_account['name']}")
                    st.write(f"**金额**: {format_currency(amount)}")
                    st.write(f"**分类**: {category} - {subcategory}")
                    if merchant:
                        st.write(f"**商家**: {merchant}")
                    if budget_id:
                        st.write(f"**预算**: {budget_label}")
                
                # 清空表单
                st.cache_data.clear()


# ============ 最近支出 ============
st.markdown("---")
st.subheader("📋 最近支出")

col_filter1, col_filter2 = st.columns(2)
with col_filter1:
    start_date = st.date_input("开始日期", value=date.today() - timedelta(days=30))
with col_filter2:
    end_date = st.date_input("结束日期", value=date.today())

try:
    expenses = api_client.get_expenses()
    
    # 过滤日期范围
    filtered_expenses = []
    for e in expenses:
        exp_date = datetime.strptime(e.get("expense_date", ""), "%Y-%m-%d").date()
        if start_date <= exp_date <= end_date:
            filtered_expenses.append(e)
    
    filtered_expenses = filtered_expenses[:10]  # 最近10笔
    
    if filtered_expenses:
        expense_data = []
        for e in filtered_expenses:
            expense_data.append({
                "日期": e.get("expense_date", ""),
                "金额": format_currency(float(e.get("amount", 0))),
                "分类": f"{e.get('category', '')}{'-'+e.get('subcategory','') if e.get('subcategory') else ''}",
                "商家": e.get("merchant", "-"),
                "ID": e.get("id"),
            })
        
        for idx, row in enumerate(expense_data):
            col_info, col_action = st.columns([5, 1])
            with col_info:
                st.text(f"{row['日期']} | {row['金额']} | {row['分类']} | {row['商家']}")
            with col_action:
                if st.button("删除", key=f"del_{row['ID']}"):
                    try:
                        api_client.delete_expense(row['ID'])
                        st.success("删除成功")
                        st.rerun()
                    except Exception as e:
                        st.error(f"删除失败: {e}")
    else:
        st.info("暂无支出记录")
except Exception as e:
    st.error(f"加载支出记录失败: {e}")
