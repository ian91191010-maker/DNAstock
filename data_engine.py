import requests
import pandas as pd
import pandas_ta as ta
import datetime
from dateutil.relativedelta import relativedelta
from functools import lru_cache # 導入快取套件，讓程式跑得更快

# ▼▼▼ 請將您的 FinMind Token 貼在下方引號內 ▼▼▼
MY_FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wNC0xMyAyMDoxMjo1NCIsInVzZXJfaWQiOiJRaWFuIiwiZW1haWwiOiJpYW45MTE5MTAxMEBnbWFpbC5jb20iLCJpcCI6IjM2LjIzOC4xMjMuMjM2In0.af0-kDmRLah5shXyXRanpqWF9jYJaRiArmWLzE5LdPU"
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

@lru_cache(maxsize=1)
def _fetch_stock_info_df(token: str) -> pd.DataFrame:
    """內部函數：下載台股總表，使用 lru_cache 確保每次開啟軟體只會下載一次，不浪費時間"""
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {"dataset": "TaiwanStockInfo"}
    if token and token != "請將您的_TOKEN_貼在這裡":
        parameter["token"] = token
    try:
        response = requests.get(url, params=parameter, timeout=10)
        data = response.json()
        if data.get("status") == 200 and data.get("data"):
            return pd.DataFrame(data["data"])
    except:
        pass
    return pd.DataFrame()

def get_stock_name(stock_id: str, token: str = MY_FINMIND_TOKEN) -> str:
    """對外開放的函數：輸入代碼，回傳中文股名"""
    df = _fetch_stock_info_df(token)
    if not df.empty:
        # 將代碼轉為字串進行精準比對
        match = df[df['stock_id'].astype(str) == str(stock_id)]
        if not match.empty:
            return match.iloc[0]['stock_name']
    return ""

def fetch_finmind_data(stock_id: str, years: float = 4, token: str = MY_FINMIND_TOKEN) -> pd.DataFrame:
    fetch_years = years + 3.0 
    end_date = datetime.date.today()
    start_date = end_date - relativedelta(years=int(fetch_years), months=int((fetch_years % 1) * 12))
    
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d")
    }
    
    if token and token != "請將您的_TOKEN_貼在這裡":
        parameter["token"] = token
        
    response = requests.get(url, params=parameter)
    data = response.json()
    
    if data["status"] != 200 or not data["data"]:
        raise ValueError(f"無法獲取 {stock_id} 的資料，請檢查代碼、網路狀態。")
        
    df = pd.DataFrame(data["data"])
    
    df.rename(columns={'Trading_Volume': 'volume', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'max': 'high', 'min': 'low'}, inplace=True)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].ffill()
    
    return df

def calculate_vr(df: pd.DataFrame, length: int = 2) -> pd.Series:
    up_vol = df['volume'].where(df['close'] > df['close'].shift(1), 0)
    down_vol = df['volume'].where(df['close'] < df['close'].shift(1), 0)
    flat_vol = df['volume'].where(df['close'] == df['close'].shift(1), 0)
    up_sum = up_vol.rolling(window=length).sum()
    down_sum = down_vol.rolling(window=length).sum()
    flat_sum = flat_vol.rolling(window=length).sum()
    vr = (up_sum + 0.5 * flat_sum) / (down_sum + 0.5 * flat_sum + 1e-9) * 100
    return vr

def process_all_indicators(df_daily: pd.DataFrame) -> pd.DataFrame:
    data_length = len(df_daily)
    if data_length < 900:
        raise ValueError(f"歷史資料嚴重不足！目前僅 {data_length} 筆，不足以支撐 ADX(300)。")

    macd_res = df_daily.ta.macd(fast=200, slow=209, signal=210)
    df_daily['MACD_DIF_1'] = macd_res['MACD_200_209_210']
    df_daily['MACD_MACD_1'] = macd_res['MACDh_200_209_210']
    df_daily['MACD_SIGNAL_1'] = macd_res['MACDs_200_209_210']
    df_daily['EMA200'] = df_daily.ta.ema(length=200)
    df_daily['EMA209'] = df_daily.ta.ema(length=209)

    adx_res = df_daily.ta.adx(length=300)
    if adx_res is None or 'ADX_300' not in adx_res.columns:
        raise ValueError("無法計算 ADX_300！")
        
    df_daily['ADX_300'] = adx_res['ADX_300']
    
    df_daily['WILLR_50'] = df_daily.ta.willr(length=50)
    df_daily['RSI_60'] = df_daily.ta.rsi(length=60)

    df_weekly = df_daily.resample('W-FRI').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
    df_weekly['VR_W_2'] = calculate_vr(df_weekly, length=2)
    
    df_monthly = df_daily.resample('ME').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
    monthly_adx = df_monthly.ta.adx(length=2)
    df_monthly['PLUS_DI_M_1'] = monthly_adx['DMP_2'] if monthly_adx is not None and 'DMP_2' in monthly_adx.columns else 0 
    df_monthly['RSI_M_4'] = df_monthly.ta.rsi(length=4)
    df_monthly['VR_M_2'] = calculate_vr(df_monthly, length=2)

    df_daily = df_daily.merge(df_weekly[['VR_W_2']], left_index=True, right_index=True, how='left')
    df_daily = df_daily.merge(df_monthly[['PLUS_DI_M_1', 'RSI_M_4', 'VR_M_2']], left_index=True, right_index=True, how='left')
    df_daily.ffill(inplace=True)

    return df_daily