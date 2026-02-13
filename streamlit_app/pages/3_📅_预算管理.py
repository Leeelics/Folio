"""
预算管理页面 - Phase 2.2
包含：预算列表、关联账户可用资金、新建预算
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import EquilibraAPIClient

st.set_page_config(page_title="预算管理", page_icon="📅", layout="wide")


@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return EquilibraAPIClient(base_url=api_url)


api_client = get_api_client()

st.title("📅 预算管理")
st.markdown("管理您的预算计划，跟踪支出进度")
st.markdown("---")


def format_currency(amount, currency="CNY"):
    """格式化货币显示"""
    symbols = {"CNY": "¥", "USD": "$", "HKD": "HK$"}
    symbol = symbols.get(currency, currency)
    return f"{symbol}{float(amount or 0):,.2f}"


def _f(val):
    """Safely convert API value (may be string/None) to float."""
    return float(val or 0)


def load_budgets(status=None):
    """加载预算列表"""
    try:
        return api_client.get_budgets(status=status)
    except Exception as e:
        st.error(f"加载预算失败: {e}")
        return []


def load_budget_available_funds(budget_id):
    """加载预算关联账户可用资金"""
    try:
        return api_client.get_budget_available_funds(budget_id)
    except Exception as e:
        st.error(f"加载可用资金失败: {e}")
        return None


def create_budget(data):
    """创建预算"""
    try:
        return api_client.create_budget(**data)
    except Exception as e:
        st.error(f"创建预算失败: {e}")
        return None


def complete_budget(budget_id):
    """完成预算"""
    try:
        return api_client.complete_budget(budget_id)
    except Exception as e:
        st.error(f"完成预算失败: {e}")
        return None


def load_accounts():
    """加载账户列表"""
    try:
        return api_client.get_accounts()
    except Exception as e:
        st.error(f"加载账户失败: {e}")
        return []


# ============ 侧边栏 ============
with st.sidebar:
    st.header("📅 预算管理")
    
    if st.button("➕ 新建预算", use_container_width=True):
        st.session_state["show_create_budget"] = True
    
    if st.button("🔄 刷新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ============ 新建预算对话框 ============
if "show_create_budget" not in st.session_state:
    st.session_state["show_create_budget"] = False

if st.session_state["show_create_budget"]:
    with st.form("budget_form"):
        st.subheader("📋 新建预算")
        
        name = st.text_input("预算名称", placeholder="如: 3月生活费")
        
        budget_type = st.selectbox(
            "预算类型",
            options=["periodic", "project"],
            format_func=lambda x: "周期性预算" if x == "periodic" else "项目型预算",
        )
        
        col1, col2 = st.columns(2)
        with col1:
            amount = st.number_input("预算金额", min_value=1.0, step=100.0)
        with col2:
            period_start = st.date_input("开始日期", value=date.today())
        
        col3, col4 = st.columns(2)
        with col3:
            period_end = st.date_input("结束日期", value=date.today())
        
        # 关联账户
        accounts = load_accounts()
        if accounts:
            account_options = {
                f"{a['name']} ({a['account_type']})": a["id"] 
                for a in accounts
            }
            selected_names = st.multiselect(
                "关联账户（可选）",
                options=list(account_options.keys()),
                help="关联后可在预算详情页查看这些账户的可用资金总额",
            )
            associated_account_ids = [account_options[n] for n in selected_names] if selected_names else None
        else:
            associated_account_ids = None
            st.caption("暂无账户可关联")
        
        notes = st.text_area("备注（可选）")
        
        col5, col6 = st.columns(2)
        with col5:
            submitted = st.form_submit_button("创建预算", type="primary")
        with col6:
            if st.form_submit_button("取消"):
                st.session_state["show_create_budget"] = False
                st.rerun()
        
        if submitted:
            if not name:
                st.error("请输入预算名称")
            elif amount <= 0:
                st.error("预算金额必须大于0")
            elif period_end < period_start:
                st.error("结束日期不能早于开始日期")
            else:
                result = create_budget({
                    "name": name,
                    "budget_type": budget_type,
                    "amount": amount,
                    "period_start": str(period_start),
                    "period_end": str(period_end),
                    "associated_account_ids": associated_account_ids,
                    "notes": notes if notes else None,
                })
                if result:
                    st.success("预算创建成功！")
                    st.session_state["show_create_budget"] = False
                    st.cache_data.clear()
                    st.rerun()
    
    st.markdown("---")


# ============ 预算统计 ============
budgets = load_budgets()
active_budgets = [b for b in budgets if b.get("status") == "active"]
completed_budgets = [b for b in budgets if b.get("status") == "completed"]
cancelled_budgets = [b for b in budgets if b.get("status") == "cancelled"]

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("进行中预算", len(active_budgets))
with col2:
    total_budget = sum(_f(b.get("amount", 0)) for b in active_budgets)
    st.metric("总预算金额", format_currency(total_budget))
with col3:
    total_spent = sum(_f(b.get("spent", 0)) for b in active_budgets)
    st.metric("总已支出", format_currency(total_spent))


# ============ 进行中的预算 ============
st.subheader("📊 进行中的预算")

if active_budgets:
    for budget in active_budgets:
        budget_id = budget["id"]
        name = budget.get("name", "")
        amount = _f(budget.get("amount", 0))
        spent = _f(budget.get("spent", 0))
        remaining = _f(budget.get("remaining", 0))
        period_start = budget.get("period_start", "")
        period_end = budget.get("period_end", "")
        
        # 计算进度
        progress = (spent / amount * 100) if amount > 0 else 0
        
        # 颜色指示
        if progress >= 100:
            color = "red"
            status = "🔴 已超支"
        elif progress >= 80:
            color = "orange"
            status = "🟡 即将超支"
        else:
            color = "green"
            status = "🟢 正常"
        
        with st.expander(f"{status} {name}", expanded=False):
            # 进度条
            st.progress(min(progress / 100, 1.0))
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("预算金额", format_currency(amount))
            with col2:
                st.metric("已支出", format_currency(spent))
            with col3:
                st.metric("剩余", format_currency(remaining))
            with col4:
                days_left = (pd.to_datetime(period_end) - pd.to_datetime(date.today())).days
                st.metric("剩余天数", f"{days_left}天")
            
            # 关联账户可用资金
            available_funds = load_budget_available_funds(budget_id)
            if available_funds:
                total_available = available_funds.get("total_available", 0)
                st.info(f"💰 关联账户可用资金总额: {format_currency(total_available)}")
                
                accounts = available_funds.get("accounts", [])
                if accounts:
                    with st.expander("查看详情"):
                        for acc in accounts:
                            st.write(
                                f"• {acc['name']} ({acc['account_type']}): "
                                f"{format_currency(acc['available_cash'])}"
                            )
            
            # 编辑预算
            if st.session_state.get(f"edit_{budget_id}"):
                with st.form(f"edit_form_{budget_id}"):
                    edit_name = st.text_input("预算名称", value=name)
                    edit_amount = st.number_input("预算金额", value=amount, min_value=1.0, step=100.0)
                    edit_start = st.date_input("开始日期", value=pd.to_datetime(period_start).date())
                    edit_end = st.date_input("结束日期", value=pd.to_datetime(period_end).date())
                    edit_notes = st.text_area("备注", value=budget.get("notes", ""))
                    
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.form_submit_button("保存", type="primary"):
                            try:
                                api_client.update_budget(
                                    budget_id,
                                    name=edit_name,
                                    amount=edit_amount,
                                    period_start=str(edit_start),
                                    period_end=str(edit_end),
                                    notes=edit_notes if edit_notes else None
                                )
                                st.success("预算已更新")
                                st.session_state[f"edit_{budget_id}"] = False
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"更新失败: {e}")
                    with col_cancel:
                        if st.form_submit_button("取消"):
                            st.session_state[f"edit_{budget_id}"] = False
                            st.rerun()
            
            # 操作按钮
            col5, col6, col7, col8 = st.columns(4)
            with col5:
                if st.button("编辑", key=f"edit_btn_{budget_id}"):
                    st.session_state[f"edit_{budget_id}"] = True
                    st.rerun()
            with col6:
                st.page_link("pages/4_📝_日常记账.py", label="📝 记一笔")
            with col7:
                if st.button("结算", key=f"complete_{budget_id}"):
                    if complete_budget(budget_id):
                        st.success("预算已结算")
                        st.cache_data.clear()
                        st.rerun()
            with col8:
                if st.button("取消", key=f"cancel_{budget_id}"):
                    try:
                        api_client.cancel_budget(budget_id)
                        st.success("预算已取消")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"取消失败: {e}")
else:
    st.info("暂无进行中的预算")


# ============ 已完成的预算 ============
st.markdown("---")
st.subheader("✅ 已完成的预算")

if completed_budgets:
    for budget in completed_budgets:
        budget_id = budget["id"]
        with st.expander(f"✓ {budget['name']}", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("预算金额", format_currency(budget.get("amount", 0)))
            with col2:
                st.metric("已支出", format_currency(budget.get("spent", 0)))
            with col3:
                st.metric("剩余", format_currency(budget.get("remaining", 0)))
            
            if st.button("删除", key=f"delete_completed_{budget_id}"):
                try:
                    api_client.delete_budget(budget_id)
                    st.success("预算已删除")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败: {e}")
else:
    st.info("暂无已完成的预算")


# ============ 已取消的预算 ============
st.markdown("---")
st.subheader("❌ 已取消的预算")

if cancelled_budgets:
    for budget in cancelled_budgets:
        budget_id = budget["id"]
        with st.expander(f"✗ {budget['name']}", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("预算金额", format_currency(budget.get("amount", 0)))
            with col2:
                st.metric("已支出", format_currency(budget.get("spent", 0)))
            with col3:
                st.metric("剩余", format_currency(budget.get("remaining", 0)))
            
            if st.button("删除", key=f"delete_cancelled_{budget_id}"):
                try:
                    api_client.delete_budget(budget_id)
                    st.success("预算已删除")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败: {e}")
else:
    st.info("暂无已取消的预算")


# ============ 预算使用率排名 ============
st.markdown("---")
st.subheader("📈 预算使用率排名")

if active_budgets:
    budget_ranking = []
    for b in active_budgets:
        usage = (_f(b.get("spent", 0)) / _f(b.get("amount", 1)) * 100) if _f(b.get("amount", 0)) > 0 else 0
        budget_ranking.append({
            "name": b["name"],
            "usage": usage,
            "remaining": b.get("remaining", 0),
        })
    
    budget_ranking.sort(key=lambda x: x["usage"], reverse=True)
    
    for i, b in enumerate(budget_ranking):
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.write(f"{i+1}. {b['name']}")
        with col2:
            st.progress(min(b["usage"] / 100, 1.0))
        with col3:
            st.write(f"{b['usage']:.1f}%")
