import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import EquilibraAPIClient

st.set_page_config(page_title="账户管理", page_icon="💰", layout="wide")


# 初始化 API 客户端
@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return EquilibraAPIClient(base_url=api_url)


api_client = get_api_client()

# 页面标题
st.title("💰 账户管理")
st.markdown("管理您的所有平台账户，支持多币种现金和持仓统一管理")
st.markdown("---")

# 刷新按钮
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🔄 刷新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ============ 加载数据 ============
@st.cache_data(ttl=60)
def load_accounts():
    """加载所有账户"""
    try:
        return api_client.get_brokerage_accounts()
    except Exception as e:
        st.error(f"加载账户失败: {e}")
        return []


@st.cache_data(ttl=60)
def load_account_view(account_id: int):
    """加载账户统一视图"""
    try:
        return api_client.get_account_unified_view(account_id)
    except Exception as e:
        st.error(f"加载账户视图失败: {e}")
        return None


@st.cache_data(ttl=60)
def load_brokerage_summary():
    """加载资产汇总"""
    try:
        return api_client.get_brokerage_summary()
    except Exception as e:
        st.error(f"加载汇总失败: {e}")
        return None


# 加载数据
accounts = load_accounts()
summary = load_brokerage_summary()

# ============ 账户概览卡片 ============
st.markdown("### 📊 账户概览")

if summary:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="总账户数", value=len(summary.get("accounts", [])))

    with col2:
        st.metric(label="总现金", value=f"¥{summary.get('total_cash_cny', 0):,.2f}")

    with col3:
        st.metric(label="总持仓", value=f"¥{summary.get('total_holdings_cny', 0):,.2f}")

    with col4:
        st.metric(label="总资产", value=f"¥{summary.get('total_assets_cny', 0):,.2f}")
else:
    st.info("暂无账户数据")

st.markdown("---")

# ============ 添加新账户 ============
st.markdown("### ➕ 添加新账户")

with st.expander("点击展开添加账户表单", expanded=False):
    col1, col2 = st.columns(2)

    with col1:
        account_name = st.text_input("账户名称", placeholder="如：富途证券")
        platform_type = st.selectbox(
            "平台类型",
            options=[
                ("bank", "银行"),
                ("securities", "证券"),
                ("fund", "基金平台"),
                ("crypto", "加密货币"),
                ("other", "其他"),
            ],
            format_func=lambda x: x[1],
        )
        institution = st.text_input("机构名称", placeholder="如：富途、招商银行")

    with col2:
        base_currency = st.selectbox("本位币", options=["CNY", "HKD", "USD", "USDT"], index=0)
        account_number = st.text_input("账号（可选）", placeholder="如：6222****")
        notes = st.text_area("备注（可选）", placeholder="其他说明信息")

    if st.button("✅ 添加账户", use_container_width=True):
        if not account_name:
            st.error("请输入账户名称")
        else:
            try:
                result = api_client.create_brokerage_account(
                    name=account_name,
                    platform_type=platform_type[0],
                    institution=institution or None,
                    account_number=account_number or None,
                    base_currency=base_currency,
                    notes=notes or None,
                )
                st.success(f"✅ 账户 '{account_name}' 创建成功！")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"创建账户失败: {e}")

st.markdown("---")

# ============ 账户列表 ============
st.markdown("### 📋 账户列表")

if not accounts:
    st.info("暂无账户，请先添加账户")
else:
    # 平台类型映射
    platform_type_map = {
        "bank": "银行",
        "securities": "证券",
        "fund": "基金平台",
        "crypto": "加密货币",
        "other": "其他",
    }

    # 显示每个账户
    for account in accounts:
        account_id = account["id"]
        account_name = account["name"]
        platform_type = platform_type_map.get(account["platform_type"], account["platform_type"])
        institution = account.get("institution", "-")

        # 获取账户详细视图
        view = load_account_view(account_id)

        # 构建展开框标题
        if view:
            title = f"**{account_name}** ({platform_type}) - 总资产: ¥{view['total_assets']:,.2f}"
        else:
            title = f"**{account_name}** ({platform_type})"

        with st.expander(title, expanded=False):
            if view:
                # 显示现金余额
                st.markdown("#### 💰 现金余额")
                if view.get("cash_balances"):
                    cash_data = []
                    for cash in view["cash_balances"]:
                        cash_data.append(
                            {
                                "币种": cash["currency"],
                                "可用": f"{cash['available']:,.2f}",
                                "冻结": f"{cash['frozen']:,.2f}",
                                "总计": f"{cash['total']:,.2f}",
                            }
                        )
                    st.dataframe(pd.DataFrame(cash_data), use_container_width=True, hide_index=True)
                else:
                    st.info("暂无现金余额")

                # 现金管理按钮
                col_cash1, col_cash2 = st.columns(2)
                with col_cash1:
                    if st.button("💵 设置余额", key=f"set_cash_{account_id}"):
                        st.session_state[f"show_set_cash_{account_id}"] = True
                with col_cash2:
                    if st.button("💸 调整余额", key=f"adjust_cash_{account_id}"):
                        st.session_state[f"show_adjust_cash_{account_id}"] = True

                # 设置余额表单
                if st.session_state.get(f"show_set_cash_{account_id}", False):
                    with st.form(key=f"set_cash_form_{account_id}"):
                        st.markdown("**设置现金余额**")
                        col1, col2 = st.columns(2)
                        with col1:
                            currency = st.selectbox(
                                "币种", ["CNY", "HKD", "USD", "USDT"], key=f"set_curr_{account_id}"
                            )
                        with col2:
                            amount = st.number_input(
                                "金额", value=0.0, step=1000.0, key=f"set_amt_{account_id}"
                            )

                        col_submit, col_cancel = st.columns(2)
                        with col_submit:
                            if st.form_submit_button("确认设置"):
                                try:
                                    api_client.set_cash_balance(account_id, currency, amount)
                                    st.success(f"余额已设置为 {amount} {currency}")
                                    st.session_state[f"show_set_cash_{account_id}"] = False
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"设置失败: {e}")
                        with col_cancel:
                            if st.form_submit_button("取消"):
                                st.session_state[f"show_set_cash_{account_id}"] = False
                                st.rerun()

                # 调整余额表单
                if st.session_state.get(f"show_adjust_cash_{account_id}", False):
                    with st.form(key=f"adjust_cash_form_{account_id}"):
                        st.markdown("**调整现金余额**")
                        col1, col2 = st.columns(2)
                        with col1:
                            currency = st.selectbox(
                                "币种", ["CNY", "HKD", "USD", "USDT"], key=f"adj_curr_{account_id}"
                            )
                        with col2:
                            delta = st.number_input(
                                "变动金额（正数增加，负数减少）",
                                value=0.0,
                                step=1000.0,
                                key=f"adj_amt_{account_id}",
                            )
                        description = st.text_input(
                            "说明", placeholder="如：充值、提现、分红", key=f"adj_desc_{account_id}"
                        )

                        col_submit, col_cancel = st.columns(2)
                        with col_submit:
                            if st.form_submit_button("确认调整"):
                                if delta != 0:
                                    try:
                                        result = api_client.adjust_cash_balance(
                                            account_id, currency, delta, description
                                        )
                                        st.success(
                                            f"余额已调整，新余额: {result['new_balance']} {currency}"
                                        )
                                        st.session_state[f"show_adjust_cash_{account_id}"] = False
                                        st.cache_data.clear()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"调整失败: {e}")
                                else:
                                    st.warning("变动金额不能为0")
                        with col_cancel:
                            if st.form_submit_button("取消"):
                                st.session_state[f"show_adjust_cash_{account_id}"] = False
                                st.rerun()

                st.markdown("---")

                # 显示持仓
                st.markdown("#### 📈 持仓列表")
                if view.get("holdings"):
                    holding_data = []
                    for holding in view["holdings"]:
                        holding_data.append(
                            {
                                "代码": holding["symbol"],
                                "名称": holding["name"],
                                "市场": holding["market"],
                                "数量": f"{holding['quantity']:,.2f}",
                                "成本价": f"{holding['avg_cost']:,.2f}",
                                "总成本": f"{holding['total_cost']:,.2f}",
                                "币种": holding["currency"],
                            }
                        )
                    st.dataframe(
                        pd.DataFrame(holding_data), use_container_width=True, hide_index=True
                    )
                else:
                    st.info("暂无持仓")

                st.markdown("---")

                # 交易录入按钮
                if st.button("📝 录入交易", key=f"trade_{account_id}"):
                    st.session_state[f"show_trade_{account_id}"] = True

                # 交易录入表单
                if st.session_state.get(f"show_trade_{account_id}", False):
                    with st.form(key=f"trade_form_{account_id}"):
                        st.markdown("**录入交易**")

                        col1, col2 = st.columns(2)
                        with col1:
                            transaction_type = st.selectbox(
                                "交易类型",
                                options=[
                                    ("buy", "买入"),
                                    ("sell", "卖出"),
                                    ("dividend", "分红"),
                                    ("transfer_in", "转入"),
                                    ("transfer_out", "转出"),
                                    ("interest", "利息"),
                                ],
                                format_func=lambda x: x[1],
                                key=f"trade_type_{account_id}",
                            )
                            asset_type = st.selectbox(
                                "资产类型",
                                options=[
                                    ("stock", "股票"),
                                    ("fund", "基金"),
                                    ("bond", "债券"),
                                    ("crypto", "加密货币"),
                                    ("commodity", "商品"),
                                ],
                                format_func=lambda x: x[1],
                                key=f"asset_type_{account_id}",
                            )
                            symbol = st.text_input(
                                "代码", placeholder="如：600000、BTC", key=f"symbol_{account_id}"
                            )
                            name = st.text_input(
                                "名称（可选）", placeholder="如：腾讯控股", key=f"name_{account_id}"
                            )

                        with col2:
                            market = st.selectbox(
                                "市场（可选）",
                                options=["", "A股", "港股", "美股", "OKX"],
                                key=f"market_{account_id}",
                            )
                            quantity = st.number_input(
                                "数量", value=0.0, step=1.0, key=f"qty_{account_id}"
                            )
                            price = st.number_input(
                                "价格", value=0.0, step=0.01, key=f"price_{account_id}"
                            )
                            fees = st.number_input(
                                "手续费", value=0.0, step=1.0, key=f"fees_{account_id}"
                            )
                            trade_currency = st.selectbox(
                                "交易币种",
                                options=["CNY", "HKD", "USD", "USDT"],
                                key=f"trade_curr_{account_id}",
                            )

                        notes = st.text_area("备注（可选）", key=f"notes_{account_id}")
                        trade_date = datetime.now()

                        col_submit, col_cancel = st.columns(2)
                        with col_submit:
                            if st.form_submit_button("确认录入"):
                                if quantity <= 0 or price < 0:
                                    st.error("数量和价格必须大于0")
                                else:
                                    try:
                                        result = api_client.create_account_transaction(
                                            account_id=account_id,
                                            asset_type=asset_type[0],
                                            symbol=symbol,
                                            transaction_type=transaction_type[0],
                                            quantity=quantity,
                                            price=price,
                                            trade_date=trade_date.isoformat(),
                                            market=market if market else None,
                                            name=name if name else None,
                                            fees=fees,
                                            trade_currency=trade_currency,
                                            notes=notes if notes else None,
                                        )
                                        st.success(f"交易录入成功！")
                                        st.session_state[f"show_trade_{account_id}"] = False
                                        st.cache_data.clear()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"交易录入失败: {e}")
                        with col_cancel:
                            if st.form_submit_button("取消"):
                                st.session_state[f"show_trade_{account_id}"] = False
                                st.rerun()

                st.markdown("---")

            # 账户操作按钮
            col_edit, col_delete = st.columns(2)

            with col_edit:
                if st.button("✏️ 编辑账户", key=f"edit_{account_id}"):
                    st.session_state[f"show_edit_{account_id}"] = True

            with col_delete:
                if st.button("🗑️ 删除账户", key=f"delete_{account_id}"):
                    st.session_state[f"confirm_delete_{account_id}"] = True

            # 编辑账户表单
            if st.session_state.get(f"show_edit_{account_id}", False):
                with st.form(key=f"edit_form_{account_id}"):
                    st.markdown("**编辑账户信息**")

                    col1, col2 = st.columns(2)
                    with col1:
                        new_name = st.text_input(
                            "账户名称", value=account["name"], key=f"edit_name_{account_id}"
                        )
                        new_institution = st.text_input(
                            "机构名称",
                            value=account.get("institution", ""),
                            key=f"edit_inst_{account_id}",
                        )
                    with col2:
                        new_account_number = st.text_input(
                            "账号",
                            value=account.get("account_number", ""),
                            key=f"edit_num_{account_id}",
                        )
                        new_notes = st.text_area(
                            "备注", value=account.get("notes", ""), key=f"edit_notes_{account_id}"
                        )

                    col_submit, col_cancel = st.columns(2)
                    with col_submit:
                        if st.form_submit_button("保存修改"):
                            try:
                                api_client.update_brokerage_account(
                                    account_id=account_id,
                                    name=new_name,
                                    institution=new_institution or None,
                                    account_number=new_account_number or None,
                                    notes=new_notes or None,
                                )
                                st.success("账户信息已更新")
                                st.session_state[f"show_edit_{account_id}"] = False
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"更新失败: {e}")
                    with col_cancel:
                        if st.form_submit_button("取消"):
                            st.session_state[f"show_edit_{account_id}"] = False
                            st.rerun()

            # 删除确认对话框
            if st.session_state.get(f"confirm_delete_{account_id}", False):
                st.warning(
                    "⚠️ **确定要删除此账户吗？**\n\n此操作将删除账户及其所有关联数据（现金余额、持仓、交易记录），且无法恢复！"
                )
                col_confirm, col_cancel = st.columns(2)

                with col_confirm:
                    if st.button("⚠️ 确认删除", key=f"confirm_del_{account_id}"):
                        try:
                            api_client.delete_brokerage_account(account_id)
                            st.success("账户已删除")
                            st.session_state[f"confirm_delete_{account_id}"] = False
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"删除失败: {e}")

                with col_cancel:
                    if st.button("取消", key=f"cancel_del_{account_id}"):
                        st.session_state[f"confirm_delete_{account_id}"] = False
                        st.rerun()

st.markdown("---")
st.markdown(
    "💡 **提示**：\n- 点击账户展开查看详情\n- 支持添加多种类型账户：银行、证券、基金、加密货币\n- 交易录入会自动联动更新现金和持仓"
)
