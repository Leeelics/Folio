"""股票行情页面 - 实时行情、市场概览、放量监控"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os
from streamlit_app.api_client import FolioAPIClient

st.set_page_config(page_title="股票行情 - Folio", page_icon="📈", layout="wide")

# 初始化 API 客户端
@st.cache_resource
def get_api_client():
    return FolioAPIClient()

client = get_api_client()

st.title("📈 股票行情")
st.markdown("实时行情查询、市场概览、放量监控")

# ============ 侧边栏 - 市场选择 ============
st.sidebar.header("市场选择")
selected_market = st.sidebar.selectbox(
    "选择市场",
    ["A股", "港股", "美股"],
    index=0
)

# 数据模式选择
mode_map = {
    "自动": "auto",
    "历史(收盘)": "daily",
    "实时": "realtime",
}
default_mode = os.getenv("STOCK_DATA_MODE", "auto").lower()
mode_labels = list(mode_map.keys())
default_index = mode_labels.index("自动")
for idx, label in enumerate(mode_labels):
    if mode_map[label] == default_mode:
        default_index = idx
        break
data_mode_label = st.sidebar.selectbox("数据模式", mode_labels, index=default_index)
data_mode = mode_map[data_mode_label]

# ============ 市场概览 ============
st.header("市场概览")

col1, col2, col3, col4 = st.columns(4)

if data_mode == "daily":
    st.info("历史模式不提供市场概览数据。")
else:
    try:
        overview = client.get_market_overview(selected_market)
        if overview and "error" not in overview:
            with col1:
                st.metric("上涨", f"{overview.get('up_count', 0)}",
                         delta=f"{overview.get('up_ratio', 0):.1f}%")
            with col2:
                st.metric("下跌", f"{overview.get('down_count', 0)}")
            with col3:
                st.metric("平盘", f"{overview.get('flat_count', 0)}")
            with col4:
                if selected_market == "A股":
                    st.metric("涨停", f"{overview.get('limit_up_count', 0)}")
                else:
                    st.metric("活跃股票", f"{overview.get('active_stocks', 0)}")

            # 涨跌比例条
            up_count = overview.get('up_count', 0)
            down_count = overview.get('down_count', 0)
            total = up_count + down_count
            if total > 0:
                up_pct = up_count / total * 100
                st.progress(up_pct / 100, text=f"涨跌比: {up_count}:{down_count}")
        else:
            st.warning("无法获取市场概览数据")
    except Exception as e:
        st.error(f"获取市场概览失败: {e}")

st.divider()

# ============ 股票搜索 ============
st.header("股票查询")

col1, col2 = st.columns([3, 1])
with col1:
    search_keyword = st.text_input("输入股票代码或名称", placeholder="如: 600000, 腾讯, AAPL")
with col2:
    search_btn = st.button("搜索", type="primary", use_container_width=True)

if data_mode == "daily":
    st.info("历史模式不提供全市场搜索，请直接用下方股票代码查询。")
elif search_keyword and search_btn:
    with st.spinner("搜索中..."):
        try:
            results = client.search_stocks(search_keyword, selected_market)
            if results and len(results) > 0:
                st.subheader("搜索结果")

                # 转换为 DataFrame
                df = pd.DataFrame(results)
                df.columns = ["代码", "名称", "市场", "当前价", "涨跌幅(%)"]

                # 添加颜色
                def color_change(val):
                    if val > 0:
                        return 'color: red'
                    elif val < 0:
                        return 'color: green'
                    return ''

                styled_df = df.style.applymap(color_change, subset=['涨跌幅(%)'])
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
            else:
                st.info("未找到匹配的股票")
        except Exception as e:
            st.error(f"搜索失败: {e}")

st.divider()

# ============ 单只股票详情 ============
st.header("股票详情")

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    stock_symbol = st.text_input("股票代码", placeholder="如: 600000")
with col2:
    stock_market = st.selectbox("市场", ["A股", "港股", "美股"], key="detail_market")
with col3:
    query_btn = st.button("查询行情", type="primary", use_container_width=True)

if stock_symbol and query_btn:
    with st.spinner("获取行情中..."):
        try:
            quote = client.get_stock_quote(stock_market, stock_symbol, mode=data_mode)
            if quote and "error" not in quote:
                # 显示行情卡片
                st.subheader(f"{quote.get('name', '')} ({quote.get('symbol', '')})")

                col1, col2, col3, col4 = st.columns(4)

                change_pct = quote.get('change_percent', 0)
                price_color = "red" if change_pct > 0 else ("green" if change_pct < 0 else "gray")

                with col1:
                    st.metric(
                        "当前价",
                        f"¥{quote.get('current_price', 0):.2f}",
                        delta=f"{change_pct:.2f}%"
                    )
                with col2:
                    st.metric("今开", f"¥{quote.get('open_price', 0):.2f}")
                with col3:
                    st.metric("最高", f"¥{quote.get('high', 0):.2f}")
                with col4:
                    st.metric("最低", f"¥{quote.get('low', 0):.2f}")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    volume = quote.get('volume', 0)
                    if volume >= 10000:
                        st.metric("成交量", f"{volume/10000:.2f}万手")
                    else:
                        st.metric("成交量", f"{volume}手")
                with col2:
                    amount = quote.get('amount', 0)
                    if amount >= 100000000:
                        st.metric("成交额", f"{amount/100000000:.2f}亿")
                    elif amount >= 10000:
                        st.metric("成交额", f"{amount/10000:.2f}万")
                    else:
                        st.metric("成交额", f"{amount:.2f}")
                with col3:
                    pe = quote.get('pe_ratio')
                    st.metric("市盈率", f"{pe:.2f}" if pe else "N/A")
                with col4:
                    pb = quote.get('pb_ratio')
                    st.metric("市净率", f"{pb:.2f}" if pb else "N/A")

                # K线图
                st.subheader("K线走势")
                period = st.selectbox("周期", ["daily", "weekly", "monthly"], format_func=lambda x: {"daily": "日K", "weekly": "周K", "monthly": "月K"}[x])

                kline_data = client.get_stock_kline(stock_market, stock_symbol, period)
                if kline_data and "data" in kline_data and len(kline_data["data"]) > 0:
                    df = pd.DataFrame(kline_data["data"])

                    fig = go.Figure(data=[go.Candlestick(
                        x=df['date'],
                        open=df['open'],
                        high=df['high'],
                        low=df['low'],
                        close=df['close'],
                        increasing_line_color='red',
                        decreasing_line_color='green'
                    )])

                    fig.update_layout(
                        title=f"{quote.get('name', '')} K线图",
                        xaxis_title="日期",
                        yaxis_title="价格",
                        xaxis_rangeslider_visible=False,
                        height=500
                    )

                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("暂无K线数据")
            else:
                st.error(f"未找到股票: {stock_symbol}")
        except Exception as e:
            st.error(f"获取行情失败: {e}")

st.divider()

# ============ 放量股票 ============
st.header("放量股票")
st.caption("成交量超过平均值2倍的股票")

col1, col2 = st.columns([1, 4])
with col1:
    threshold = st.number_input("放量倍数", min_value=1.5, max_value=10.0, value=2.0, step=0.5)
    refresh_btn = st.button("刷新", key="refresh_volume")

if data_mode == "daily":
    st.info("历史模式不提供放量股票数据。")
else:
    if refresh_btn or "volume_surge_loaded" not in st.session_state:
        st.session_state.volume_surge_loaded = True
        with st.spinner("获取放量股票..."):
            try:
                surge_stocks = client.get_volume_surge_stocks(selected_market, threshold)
                if surge_stocks and len(surge_stocks) > 0:
                    df = pd.DataFrame(surge_stocks)
                    df.columns = ["代码", "名称", "当前价", "涨跌幅(%)", "成交量", "量比", "成交额"]

                    # 格式化
                    df["涨跌幅(%)"] = df["涨跌幅(%)"].apply(lambda x: f"{x:.2f}")
                    df["量比"] = df["量比"].apply(lambda x: f"{x:.2f}")

                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("暂无放量股票数据")
            except Exception as e:
                st.error(f"获取放量股票失败: {e}")

# ============ 自选股 ============
st.divider()
st.header("自选股")

# 添加自选股
with st.expander("添加自选股"):
    col1, col2, col3 = st.columns(3)
    with col1:
        watch_symbol = st.text_input("股票代码", key="watch_symbol")
    with col2:
        watch_market = st.selectbox("市场", ["A股", "港股", "美股"], key="watch_market")
    with col3:
        watch_notes = st.text_input("备注", key="watch_notes")

    if st.button("添加到自选", type="primary"):
        if watch_symbol:
            try:
                result = client.add_to_watchlist(watch_symbol, watch_market, watch_notes)
                if result and "error" not in result:
                    st.success(f"已添加 {watch_symbol} 到自选股")
                    st.rerun()
                else:
                    st.error("添加失败")
            except Exception as e:
                st.error(f"添加失败: {e}")
        else:
            st.warning("请输入股票代码")

# 显示自选股列表
try:
    watchlist = client.get_watchlist()
    if watchlist and "watchlist" in watchlist and len(watchlist["watchlist"]) > 0:
        st.subheader("我的自选")

        for item in watchlist["watchlist"]:
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])

            with col1:
                st.write(f"**{item.get('name', item.get('symbol'))}**")
                st.caption(f"{item.get('market')} | {item.get('symbol')}")

            with col2:
                price = item.get('current_price')
                if price:
                    st.write(f"¥{price:.2f}")
                else:
                    st.write("--")

            with col3:
                change = item.get('change_percent')
                if change is not None:
                    color = "red" if change > 0 else ("green" if change < 0 else "gray")
                    st.markdown(f"<span style='color:{color}'>{change:.2f}%</span>", unsafe_allow_html=True)
                else:
                    st.write("--")

            with col4:
                st.caption(item.get('notes', ''))

            with col5:
                if st.button("删除", key=f"del_watch_{item.get('id')}"):
                    try:
                        client.remove_from_watchlist(item.get('id'))
                        st.rerun()
                    except Exception as e:
                        st.error(f"删除失败: {e}")
    else:
        st.info("暂无自选股，点击上方添加")
except Exception as e:
    st.error(f"获取自选股失败: {e}")

# 页脚
st.divider()
st.caption(f"数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据来源: AkShare")
