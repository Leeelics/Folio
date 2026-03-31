import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from streamlit_app.api_client import FolioAPIClient

st.set_page_config(page_title="报表与数据管理", page_icon="📊", layout="wide")

# 初始化 API 客户端
api = FolioAPIClient()

st.title("📊 报表与数据管理")

# 创建 5 个 Tab
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 投资业绩报表",
    "💰 支出汇总报表",
    "📸 账户快照",
    "📤 数据导出",
    "📥 数据导入"
])

# ============ Tab 1: 投资业绩报表 ============
with tab1:
    st.header("投资业绩报表")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "开始日期",
            value=date.today() - timedelta(days=30),
            key="perf_start"
        )
    with col2:
        end_date = st.date_input(
            "结束日期",
            value=date.today(),
            key="perf_end"
        )

    if st.button("生成投资业绩报表", type="primary"):
        try:
            report = api.get_investment_performance_report(
                start_date.isoformat(),
                end_date.isoformat()
            )

            # 显示关键指标
            summary = report["summary"]
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("总成本", f"¥{float(summary['total_cost']):,.2f}")
            with col2:
                st.metric("总市值", f"¥{float(summary['total_market_value']):,.2f}")
            with col3:
                pnl = float(summary['total_pnl'])
                st.metric(
                    "总盈亏",
                    f"¥{pnl:,.2f}",
                    delta=f"{summary['total_pnl_pct']}%"
                )
            with col4:
                st.metric("分红收入", f"¥{float(summary['dividend_income']):,.2f}")

            # 持仓 P&L 表格
            st.subheader("持仓盈亏明细")
            if report["holdings"]:
                df = pd.DataFrame(report["holdings"])
                df["pnl_numeric"] = df["pnl"].astype(float)

                # 格式化显示
                display_df = df[[
                    "symbol", "name", "asset_type", "quantity",
                    "avg_cost", "current_price", "cost", "market_value",
                    "pnl", "pnl_pct", "account"
                ]].copy()

                st.dataframe(display_df, use_container_width=True)

                # 资产配置饼图
                st.subheader("资产配置")
                asset_allocation = df.groupby("asset_type")["market_value"].apply(
                    lambda x: x.astype(float).sum()
                ).reset_index()

                fig = px.pie(
                    asset_allocation,
                    values="market_value",
                    names="asset_type",
                    title="按资产类型分配"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("期间内无持仓数据")

        except Exception as e:
            st.error(f"生成报表失败: {e}")

# ============ Tab 2: 支出汇总报表 ============
with tab2:
    st.header("支出汇总报表")

    col1, col2, col3 = st.columns(3)
    with col1:
        exp_start_date = st.date_input(
            "开始日期",
            value=date.today() - timedelta(days=30),
            key="exp_start"
        )
    with col2:
        exp_end_date = st.date_input(
            "结束日期",
            value=date.today(),
            key="exp_end"
        )
    with col3:
        category_filter = st.text_input("分类筛选（可选）", key="exp_category")

    if st.button("生成支出汇总报表", type="primary"):
        try:
            report = api.get_expense_summary_report(
                exp_start_date.isoformat(),
                exp_end_date.isoformat(),
                category_filter if category_filter else None
            )

            # 显示关键指标
            summary = report["summary"]
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("总支出", f"¥{float(summary['total_amount']):,.2f}")
            with col2:
                st.metric("支出笔数", summary['expense_count'])
            with col3:
                st.metric("日均支出", f"¥{float(summary['daily_avg']):,.2f}")
            with col4:
                st.metric("分类数量", summary['category_count'])

            # 分类明细柱状图
            st.subheader("分类支出明细")
            if report["category_breakdown"]:
                df_cat = pd.DataFrame(report["category_breakdown"])

                fig = px.bar(
                    df_cat,
                    x="category",
                    y="amount",
                    title="各分类支出金额",
                    labels={"amount": "金额 (¥)", "category": "分类"}
                )
                fig.update_traces(
                    text=df_cat["amount"].apply(lambda x: f"¥{float(x):,.0f}"),
                    textposition="outside"
                )
                st.plotly_chart(fig, use_container_width=True)

                # 分类明细表格
                st.dataframe(df_cat, use_container_width=True)

            # 每日趋势折线图
            st.subheader("每日支出趋势")
            if report["daily_trend"]:
                df_trend = pd.DataFrame(report["daily_trend"])
                df_trend["amount_numeric"] = df_trend["amount"].astype(float)

                fig = px.line(
                    df_trend,
                    x="date",
                    y="amount_numeric",
                    title="每日支出趋势",
                    labels={"amount_numeric": "金额 (¥)", "date": "日期"}
                )
                st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"生成报表失败: {e}")

# ============ Tab 3: 账户快照 ============
with tab3:
    st.header("账户快照")

    snapshot_date = st.date_input(
        "快照日期",
        value=date.today(),
        key="snapshot_date"
    )

    if st.button("生成账户快照", type="primary"):
        try:
            report = api.get_account_snapshot_report(snapshot_date.isoformat())

            # 显示净资产指标（大号显示）
            summary = report["summary"]
            st.markdown("### 净资产总览")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("总余额", f"¥{float(summary['total_balance']):,.2f}")
            with col2:
                st.metric("总持仓市值", f"¥{float(summary['total_holdings_value']):,.2f}")
            with col3:
                net_worth = float(summary['total_net_worth'])
                st.metric(
                    "净资产",
                    f"¥{net_worth:,.2f}",
                    help="余额 + 持仓市值"
                )

            # 账户表格
            st.subheader("账户明细")
            if report["accounts"]:
                df_accounts = pd.DataFrame(report["accounts"])
                display_cols = [
                    "name", "type", "institution", "balance",
                    "holdings_value", "net_worth", "currency"
                ]
                st.dataframe(
                    df_accounts[display_cols],
                    use_container_width=True
                )

            # 持仓表格
            st.subheader("持仓明细")
            if report["holdings"]:
                df_holdings = pd.DataFrame(report["holdings"])
                display_cols = [
                    "symbol", "name", "asset_type", "quantity",
                    "avg_cost", "current_price", "market_value",
                    "pnl", "currency"
                ]
                st.dataframe(
                    df_holdings[display_cols],
                    use_container_width=True
                )

                # 资产配置饼图
                st.subheader("资产配置")
                asset_allocation = df_holdings.groupby("asset_type")["market_value"].apply(
                    lambda x: x.astype(float).sum()
                ).reset_index()

                fig = px.pie(
                    asset_allocation,
                    values="market_value",
                    names="asset_type",
                    title="按资产类型分配"
                )
                st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"生成快照失败: {e}")

# ============ Tab 4: 数据导出 ============
with tab4:
    st.header("数据导出")

    # 交易记录导出
    with st.expander("📊 交易记录导出", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            tx_start = st.date_input("开始日期", key="tx_export_start")
        with col2:
            tx_end = st.date_input("结束日期", key="tx_export_end")
        with col3:
            tx_asset_type = st.selectbox(
                "资产类型（可选）",
                ["全部", "stock", "fund", "bond", "bank_product", "crypto"],
                key="tx_asset_type"
            )

        if st.button("导出交易记录 CSV", key="export_tx"):
            try:
                asset_type = None if tx_asset_type == "全部" else tx_asset_type
                csv_data = api.export_transactions(
                    tx_start.isoformat(),
                    tx_end.isoformat(),
                    asset_type
                )
                st.download_button(
                    label="下载 CSV 文件",
                    data=csv_data,
                    file_name=f"transactions_{tx_start}_{tx_end}.csv",
                    mime="text/csv"
                )
                st.success("导出成功！点击上方按钮下载")
            except Exception as e:
                st.error(f"导出失败: {e}")

    # 支出记录导出
    with st.expander("💰 支出记录导出"):
        col1, col2, col3 = st.columns(3)
        with col1:
            exp_export_start = st.date_input("开始日期", key="exp_export_start")
        with col2:
            exp_export_end = st.date_input("结束日期", key="exp_export_end")
        with col3:
            exp_export_cat = st.text_input("分类筛选（可选）", key="exp_export_cat")

        if st.button("导出支出记录 CSV", key="export_exp"):
            try:
                csv_data = api.export_expenses(
                    exp_export_start.isoformat(),
                    exp_export_end.isoformat(),
                    exp_export_cat if exp_export_cat else None
                )
                st.download_button(
                    label="下载 CSV 文件",
                    data=csv_data,
                    file_name=f"expenses_{exp_export_start}_{exp_export_end}.csv",
                    mime="text/csv"
                )
                st.success("导出成功！点击上方按钮下载")
            except Exception as e:
                st.error(f"导出失败: {e}")

    # 持仓快照导出
    with st.expander("📸 持仓快照导出"):
        holding_date = st.date_input("快照日期", key="holding_export_date")

        if st.button("导出持仓快照 CSV", key="export_holding"):
            try:
                csv_data = api.export_holdings(holding_date.isoformat())
                st.download_button(
                    label="下载 CSV 文件",
                    data=csv_data,
                    file_name=f"holdings_snapshot_{holding_date}.csv",
                    mime="text/csv"
                )
                st.success("导出成功！点击上方按钮下载")
            except Exception as e:
                st.error(f"导出失败: {e}")

    # 账户列表导出
    with st.expander("🏦 账户列表导出"):
        if st.button("导出账户列表 CSV", key="export_accounts"):
            try:
                csv_data = api.export_accounts()
                st.download_button(
                    label="下载 CSV 文件",
                    data=csv_data,
                    file_name=f"accounts_{date.today()}.csv",
                    mime="text/csv"
                )
                st.success("导出成功！点击上方按钮下载")
            except Exception as e:
                st.error(f"导出失败: {e}")

# ============ Tab 5: 数据导入 ============
with tab5:
    st.header("数据导入")

    # 交易记录导入
    with st.expander("📊 交易记录导入", expanded=True):
        st.markdown("**CSV 模板格式：**")
        st.code("""date,symbol,name,asset_type,type,quantity,price,fees,currency,notes
2026-01-15,600000,浦发银行,stock,buy,100,10.50,5.00,CNY,
2026-01-20,00700,腾讯控股,stock,buy,50,350.00,10.00,HKD,""")

        st.markdown("**必填列：** date, symbol, type, quantity, price")

        tx_file = st.file_uploader("上传 CSV 文件", type=["csv"], key="tx_import_file")
        tx_account = st.text_input("账户名称", key="tx_import_account")

        if st.button("导入交易记录", key="import_tx") and tx_file and tx_account:
            try:
                result = api.import_transactions(
                    tx_file.read(),
                    tx_file.name,
                    tx_account
                )

                col1, col2 = st.columns(2)
                with col1:
                    st.success(f"成功导入 {result['success_count']} 条记录")
                with col2:
                    if result['error_count'] > 0:
                        st.error(f"失败 {result['error_count']} 条记录")

                if result['errors']:
                    st.subheader("错误详情")
                    df_errors = pd.DataFrame(result['errors'])
                    st.dataframe(df_errors, use_container_width=True)

            except Exception as e:
                st.error(f"导入失败: {e}")

    # 支出记录导入
    with st.expander("💰 支出记录导入"):
        st.markdown("**CSV 模板格式：**")
        st.code("""date,amount,category,subcategory,merchant,payment_method,is_shared,notes
2026-01-15,50.00,餐饮,午餐,麦当劳,微信支付,false,
2026-01-20,1200.00,住房,房租,链家,银行转账,true,1月房租""")

        st.markdown("**必填列：** date, amount, category")

        exp_file = st.file_uploader("上传 CSV 文件", type=["csv"], key="exp_import_file")

        # 获取账户列表
        try:
            accounts = api.get_accounts()
            account_options = {f"{acc['name']} (ID: {acc['id']})": acc['id'] for acc in accounts}
            selected_account = st.selectbox("选择账户", list(account_options.keys()), key="exp_import_account")
            exp_account_id = account_options[selected_account]
        except:
            st.warning("无法加载账户列表")
            exp_account_id = st.number_input("账户 ID", min_value=1, key="exp_import_account_id")

        if st.button("导入支出记录", key="import_exp") and exp_file:
            try:
                result = api.import_expenses(
                    exp_file.read(),
                    exp_file.name,
                    exp_account_id
                )

                col1, col2 = st.columns(2)
                with col1:
                    st.success(f"成功导入 {result['success_count']} 条记录")
                with col2:
                    if result['error_count'] > 0:
                        st.error(f"失败 {result['error_count']} 条记录")

                if result['errors']:
                    st.subheader("错误详情")
                    df_errors = pd.DataFrame(result['errors'])
                    st.dataframe(df_errors, use_container_width=True)

            except Exception as e:
                st.error(f"导入失败: {e}")

    # 券商对账单导入
    with st.expander("🏦 券商对账单导入"):
        st.markdown("**CSV 模板格式（通用）：**")
        st.code("""date,symbol,name,type,quantity,price,fees,currency
2026-01-15,600000,浦发银行,buy,100,10.50,5.00,CNY
2026-01-20,600000,浦发银行,sell,50,11.00,2.50,CNY
2026-01-25,600000,浦发银行,dividend,100,0.50,0,CNY""")

        st.markdown("**必填列：** date, symbol, type, quantity, price")

        broker_file = st.file_uploader("上传 CSV 文件", type=["csv"], key="broker_import_file")
        col1, col2 = st.columns(2)
        with col1:
            broker_name = st.text_input("券商名称", placeholder="如：富途、老虎证券", key="broker_name")
        with col2:
            broker_account = st.text_input("账户名称", key="broker_account")

        if st.button("导入券商对账单", key="import_broker") and broker_file and broker_name and broker_account:
            try:
                result = api.import_brokerage_statement(
                    broker_file.read(),
                    broker_file.name,
                    broker_name,
                    broker_account
                )

                col1, col2 = st.columns(2)
                with col1:
                    st.success(f"成功导入 {result['success_count']} 条记录")
                with col2:
                    if result['error_count'] > 0:
                        st.error(f"失败 {result['error_count']} 条记录")

                if result['errors']:
                    st.subheader("错误详情")
                    df_errors = pd.DataFrame(result['errors'])
                    st.dataframe(df_errors, use_container_width=True)

            except Exception as e:
                st.error(f"导入失败: {e}")
