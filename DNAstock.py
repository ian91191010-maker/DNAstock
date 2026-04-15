import streamlit as st
import streamlit.components.v1 as components
import json
import pandas as pd
import numpy as np
import datetime
from dateutil.relativedelta import relativedelta
from data_engine import fetch_finmind_data, process_all_indicators, get_stock_name

# 設定頁面
st.set_page_config(page_title="飆股DNA指標", layout="wide")

# 1. 修改主題：字體置中，大小縮小約50% (使用 HTML 標籤替代原本的 st.title)
st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>飆股DNA指標</h3>", unsafe_allow_html=True)

with st.sidebar:
    st.header("參數設定")
    stock_id = st.text_input("輸入股票代碼", value="")
    years = st.slider("顯示資料區間 (年)", min_value=2.5, max_value=4.0, value=4.0, step=0.5)
    run_btn = st.button("執行分析")

if run_btn:
    if not stock_id:
        st.warning("⚠️ 請先在左側輸入股票代碼！")
    else:
        with st.spinner(f"正在獲取 {stock_id} 資料並生成五重乾淨圖表..."):
            try:
                stock_name = get_stock_name(stock_id)
                display_title = f"{stock_id} {stock_name}" if stock_name else stock_id
                
                df = fetch_finmind_data(stock_id, years=years)
                df_final = process_all_indicators(df)
                
                df_final = df_final[~df_final.index.duplicated(keep='last')]
                df_final.sort_index(ascending=True, inplace=True)
                
                cutoff_date = pd.to_datetime(datetime.date.today() - relativedelta(years=int(years), months=int((years % 1) * 12)))
                df_final = df_final[df_final.index >= cutoff_date]
                
                df_final.replace([np.inf, -np.inf], np.nan, inplace=True)
                df_final.dropna(inplace=True)
                
                if df_final.empty:
                    st.error("⚠️ 警告：該區間內沒有產生有效的數據！")
                    st.stop()
                    
                df_final['time'] = df_final.index.strftime('%Y-%m-%d')
                
                wr_data = []
                score_data = []
                volume_dict = {} 
                
                for index, row in df_final.iterrows():
                    date_str = row['time']
                    volume_dict[date_str] = int(row['volume'])
                    
                    wr_val = row['WILLR_50']
                    m3_pass = wr_val > -20
                    
                    s1 = 1 if row['PLUS_DI_M_1'] > 50 else 0
                    s2 = 1 if row['RSI_M_4'] > 77 else 0
                    s3 = 1 if m3_pass else 0
                    s4 = 1 if row['RSI_60'] > 57 else 0
                    s5 = 1 if row['VR_W_2'] >= 150 else 0
                    s6 = 1 if row['VR_M_2'] >= 150 else 0
                    
                    m4_score = s1 + s2 + s3 + s4 + s5 + s6
                    m4_pass = m4_score >= 3
                    
                    wr_data.append({'time': date_str, 'value': wr_val})
                    score_data.append({
                        'time': date_str, 
                        'value': m4_score,
                        'color': 'rgba(38, 166, 154, 0.8)' if m4_pass else 'rgba(239, 83, 80, 0.8)' 
                    })
                
                candles_data = df_final[['time', 'open', 'high', 'low', 'close']].to_dict(orient='records')
                ema200_data = df_final[['time', 'EMA200']].rename(columns={'EMA200': 'value'}).to_dict(orient='records')
                ema209_data = df_final[['time', 'EMA209']].rename(columns={'EMA209': 'value'}).to_dict(orient='records')
                dif_data = df_final[['time', 'MACD_DIF_1']].rename(columns={'MACD_DIF_1': 'value'}).to_dict(orient='records')
                adx_data = df_final[['time', 'ADX_300']].rename(columns={'ADX_300': 'value'}).to_dict(orient='records')

                candles_json = json.dumps(candles_data)
                ema200_json = json.dumps(ema200_data)
                ema209_json = json.dumps(ema209_data)
                dif_json = json.dumps(dif_data)
                adx_json = json.dumps(adx_data)
                wr_json = json.dumps(wr_data)
                score_json = json.dumps(score_data)
                volume_json = json.dumps(volume_dict)

                html_code = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
                    <style>
                        body {{ margin: 0; padding: 0; background-color: #131722; color: white; font-family: sans-serif; }}
                        #tvchart-container {{ position: relative; width: 100%; height: 1000px; }}
                        #tvchart {{ width: 100%; height: 100% }} 
                        #tooltip {{
                            position: absolute;
                            z-index: 1000;
                            /* 3. 標記背景虛化(半透明)，並加入毛玻璃效果 */
                            background: rgba(19, 23, 34, 0.4);
                            backdrop-filter: blur(4px);
                            padding: 8px 12px;
                            border-radius: 4px;
                            border: 1px solid rgba(43, 43, 67, 0.5);
                            display: none;
                            pointer-events: none;
                            font-size: 14px;
                            line-height: 1.5;
                        }}
                        #chart-title {{
                            position: absolute;
                            top: 15px;
                            left: 0;
                            width: 100%;
                            text-align: center;
                            z-index: 10;
                            /* 浮水印標題同步改小，淡化以免影響視覺 */
                            color: rgba(224, 227, 235, 0.2);
                            font-size: 20px; 
                            font-weight: bold;
                            pointer-events: none;
                            letter-spacing: 4px;
                        }}
                    </style>
                </head>
                <body>
                    <div id="tvchart-container">
                        <div id="chart-title">{display_title}</div>
                        <div id="tooltip"></div>
                        <div id="tvchart"></div>
                    </div>
                    <script>
                        try {{
                            const chart = LightweightCharts.createChart(document.getElementById('tvchart'), {{
                                layout: {{ background: {{ type: 'solid', color: '#131722' }}, textColor: '#d1d4dc' }},
                                grid: {{ vertLines: {{ color: '#2B2B43' }}, horzLines: {{ color: '#2B2B43' }} }},
                                crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                                rightPriceScale: {{ borderColor: '#2B2B43' }},
                                timeScale: {{ 
                                    borderColor: '#2B2B43', 
                                    barSpacing: 3, 
                                    timeVisible: true,
                                    rightOffset: 80
                                }},
                                // 2. 解決手機無法順利向下滑動頁面的問題
                                handleScroll: {{
                                    vertTouchDrag: false, // 關閉垂直拖拽，把垂直滑動權限還給瀏覽器
                                }}
                            }});

                            // 4. 重新設定 scaleMargins，將圖表間隔縮小約 50%
                            // 1. 主圖
                            chart.priceScale('right').applyOptions({{ scaleMargins: {{ top: 0.0, bottom: 0.52 }} }});
                            const candlestickSeries = chart.addCandlestickSeries({{
                                upColor: '#ef5350', downColor: '#26a69a', borderVisible: false, wickUpColor: '#ef5350', wickDownColor: '#26a69a'
                            }});
                            candlestickSeries.setData({candles_json});

                            const ema200Series = chart.addLineSeries({{ color: '#f5c211', lineWidth: 2, title: 'EMA 200' }});
                            ema200Series.setData({ema200_json});
                            const ema209Series = chart.addLineSeries({{ color: '#e0591b', lineWidth: 2, title: 'EMA 209' }});
                            ema209Series.setData({ema209_json});

                            // 2. DIF
                            const difSeries = chart.addLineSeries({{ color: '#2962FF', lineWidth: 2, title: 'DIF', priceScaleId: 'dif_scale' }});
                            chart.priceScale('dif_scale').applyOptions({{ scaleMargins: {{ top: 0.49, bottom: 0.39 }} }});
                            difSeries.setData({dif_json});

                            // 3. ADX
                            const adxSeries = chart.addLineSeries({{ color: '#FF1493', lineWidth: 2, title: 'ADX', priceScaleId: 'adx_scale' }});
                            chart.priceScale('adx_scale').applyOptions({{ scaleMargins: {{ top: 0.62, bottom: 0.26 }} }});
                            adxSeries.setData({adx_json});

                            // 4. W%R
                            const wrSeries = chart.addLineSeries({{ color: '#00BCD4', lineWidth: 2, title: 'W%R', priceScaleId: 'wr_scale' }});
                            chart.priceScale('wr_scale').applyOptions({{ scaleMargins: {{ top: 0.75, bottom: 0.13 }} }});
                            wrSeries.setData({wr_json});
                            wrSeries.createPriceLine({{ price: -20, color: '#FF9800', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: '-20' }});

                            // 5. 六大跡象得分
                            const scoreSeries = chart.addHistogramSeries({{ title: 'Score', priceScaleId: 'score_scale' }});
                            chart.priceScale('score_scale').applyOptions({{ scaleMargins: {{ top: 0.88, bottom: 0.0 }} }});
                            scoreSeries.setData({score_json});
                            scoreSeries.createPriceLine({{ price: 3, color: '#FFEB3B', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible: true, title: '3' }});

                            chart.timeScale().fitContent();

                            const tooltip = document.getElementById('tooltip');
                            const volumeData = {volume_json};

                            chart.subscribeCrosshairMove(function(param) {{
                                if (
                                    param.point === undefined ||
                                    !param.time ||
                                    param.point.x < 0 ||
                                    param.point.x > document.getElementById('tvchart-container').clientWidth ||
                                    param.point.y < 0 ||
                                    param.point.y > document.getElementById('tvchart-container').clientHeight
                                ) {{
                                    tooltip.style.display = 'none';
                                }} else {{
                                    let dateStr = param.time;
                                    if (typeof dateStr === 'object') {{
                                        dateStr = dateStr.year + '-' + 
                                                  dateStr.month.toString().padStart(2, '0') + '-' + 
                                                  dateStr.day.toString().padStart(2, '0');
                                    }}
                                    
                                    const data = param.seriesData.get(candlestickSeries);
                                    if (data) {{
                                        const open = data.open.toFixed(2);
                                        const high = data.high.toFixed(2);
                                        const low = data.low.toFixed(2);
                                        const close = data.close.toFixed(2);
                                        
                                        const vol = volumeData[dateStr];
                                        const volStr = vol !== undefined ? vol.toLocaleString() : 'N/A';
                                        
                                        tooltip.style.display = 'block';
                                        
                                        // 3. 調整 Tooltip 位置，讓它跟著十字游標走，顯示在線的下方偏右
                                        tooltip.style.left = param.point.x + 15 + 'px';
                                        tooltip.style.top = param.point.y + 15 + 'px'; 
                                        
                                        tooltip.innerHTML = `
                                            <div style="font-weight: bold; color: #FFFFFF; font-size: 16px; margin-bottom: 4px;">${{dateStr}}</div>
                                            <div style="color: #d1d4dc;">開盤: <span style="color: #FFF;">${{open}}</span></div>
                                            <div style="color: #d1d4dc;">最高: <span style="color: #FFF;">${{high}}</span></div>
                                            <div style="color: #d1d4dc;">最低: <span style="color: #FFF;">${{low}}</span></div>
                                            <div style="color: #d1d4dc;">收盤: <span style="color: #FFF;">${{close}}</span></div>
                                            <div style="color: #d1d4dc;">成交量: <span style="color: #FFF;">${{volStr}}</span></div>
                                        `;
                                    }}
                                }}
                            }});

                        }} catch (error) {{
                            document.getElementById('tvchart').innerHTML = "<h3 style='padding: 20px; color: #ff4d4f;'>前端圖表繪製失敗，錯誤原因：" + error.message + "</h3>";
                        }}
                    </script>
                </body>
                </html>
                """
                
                components.html(html_code, height=1020, scrolling=False)
                
            except Exception as e:
                st.error(f"發生錯誤：{e}")
