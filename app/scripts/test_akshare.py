import akshare as ak

stock_zh_a_hist_df = ak.stock_zh_a_hist(symbol="002714", period="daily", start_date="20260201", end_date='20260207', adjust="")
print(stock_zh_a_hist_df)

# def try_call(name, fn):
#     try:
#         df = fn()
#         print(name, "OK", df.shape, list(df.columns)[:8])
#     except Exception as e:
#         print(name, "ERR", type(e).__name__, e)

# for name, fn in [
#     ("A_EM", ak.stock_zh_a_spot_em),
#     ("A_Sina", ak.stock_zh_a_spot),
#     ("HK_EM", ak.stock_hk_spot_em),
#     ("HK_Sina", ak.stock_hk_spot),
#     ("US_EM", ak.stock_us_spot_em),
#     ("US_Sina", ak.stock_us_spot),
# ]:
#     try_call(name, fn)
