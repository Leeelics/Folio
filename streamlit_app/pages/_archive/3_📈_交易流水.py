import streamlit as st
import pandas as pd
import sys
import os

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import FolioAPIClient

st.set_page_config(page_title="交易流水", page_icon="📈", layout="wide")

# 初始化 API 客户端
@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return FolioAPIClient(base_url=api_url)

api_client = get_api_client()

st.title("📈 交易流水")
st.markdown("---")

# 婚礼支出统计
st.markdown("### 💍 婚礼支出统计")

try:
    portfolio = api_client.get_portfolio_status()
    wedding_finance = portfolio['wedding_finance']

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="婚礼总预算",
            value=f"¥{wedding_finance['wedding_budget']:,.2f}"
        )

    with col2:
        st.metric(
            label="已支出",
            value=f"¥{wedding_finance['spent']:,.2f}"
        )

    with col3:
        spent_pct = (wedding_finance['spent'] / wedding_finance['wedding_budget'] * 100) if wedding_finance['wedding_budget'] > 0 else 0
        st.metric(
            label="支出比例",
            value=f"{spent_pct:.1f}%"
        )

    with col4:
        st.metric(
            label="剩余预算",
            value=f"¥{wedding_finance['remaining_budget']:,.2f}"
        )

except Exception as e:
    st.error(f"❌ 无法加载婚礼支出数据: {str(e)}")

st.markdown("---")

# 交易记录（模拟数据，因为后端还没有交易查询接口）
st.markdown("### 📋 交易记录")

# 筛选器
col1, col2, col3 = st.columns(3)

with col1:
    transaction_type = st.selectbox(
        "交易类型",
        ["全部", "收入", "支出", "转账"]
    )

with col2:
    is_wedding = st.selectbox(
        "婚礼支出",
        ["全部", "仅婚礼支出", "非婚礼支出"]
    )

with col3:
    date_range = st.date_input(
        "日期范围",
        value=[]
    )

st.markdown("---")

# 模拟交易数据（实际应该从后端 API 获取）
st.info("🚧 交易记录功能正在开发中，以下为示例数据")

sample_data = pd.DataFrame({
    "日期": ["2026-01-04", "2026-01-03", "2026-01-02", "2026-01-01"],
    "交易类型": ["支出", "收入", "支出", "支出"],
    "金额": [5000.00, 20000.00, 3000.00, 15000.00],
    "分类": ["婚礼", "工资", "生活", "婚礼"],
    "从账户": ["银行-招商", "-", "银行-招商", "银行-工商"],
    "到账户": ["-", "银行-招商", "-", "-"],
    "描述": ["婚礼场地定金", "月度工资", "日常开销", "婚纱摄影"],
    "婚礼支出": ["✅", "❌", "❌", "✅"]
})

# 显示表格
st.dataframe(
    sample_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "金额": st.column_config.NumberColumn(
            "金额",
            format="¥%.2f"
        ),
        "婚礼支出": st.column_config.TextColumn(
            "婚礼支出",
            width="small"
        )
    }
)

st.markdown("---")

# 添加交易记录
st.markdown("### ➕ 添加交易记录")

with st.expander("添加新交易", expanded=False):
    col1, col2 = st.columns(2)

    with col1:
        new_type = st.selectbox("交易类型", ["收入", "支出", "转账"])
        new_amount = st.number_input("金额", min_value=0.0, step=100.0)
        new_category = st.text_input("分类")

    with col2:
        new_from = st.text_input("从账户")
        new_to = st.text_input("到账户")
        new_is_wedding = st.checkbox("标记为婚礼支出")

    new_description = st.text_area("描述")

    if st.button("💾 保存交易", use_container_width=True):
        st.info("🚧 此功能正在开发中，需要后端 API 支持")

st.markdown("---")

# 统计图表
st.markdown("### 📊 支出分析")

col1, col2 = st.columns(2)

with col1:
    st.info("🚧 月度支出趋势图（开发中）")

with col2:
    st.info("🚧 支出分类占比图（开发中）")
