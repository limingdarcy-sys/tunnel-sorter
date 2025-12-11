import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io

# 設定網頁標題與寬度
st.set_page_config(page_title="隧道斷面點位重排工具", layout="wide")

st.title("🚇 隧道斷面點位重排工具")
st.markdown("""
此工具可將隧道斷面點位重新排序：
1. **順時針** 排列。
2. 以 **第三象限最靠近 Y 軸** 的點為起點。
3. 支援包含 value 值的多欄位資料 (如 `node, x1, y2, x2, y2, value1...`)。
""")

# --- 側邊欄：檔案上傳與設定 ---
st.sidebar.header("1. 上傳資料")
uploaded_file = st.sidebar.file_uploader("請上傳 CSV 或 TXT 檔", type=['csv', 'txt'])

if uploaded_file is not None:
    try:
        # 嘗試讀取檔案
        # 為了處理不同分隔符號，先讀成字串再讓 pandas 判斷
        content = uploaded_file.getvalue().decode("utf-8")
        
        # 簡單判斷分隔符號：如果有逗號就用逗號，否則用空白/Tab
        sep = ',' if ',' in content else None
        
        df = pd.read_csv(io.StringIO(content), sep=sep, engine='python')
        
        # 移除欄位名稱的空白
        df.columns = [c.strip() for c in df.columns]
        
        st.sidebar.header("2. 欄位設定")
        
        # 自動猜測 X 和 Y 欄位
        all_cols = df.columns.tolist()
        
        # 猜測邏輯：優先找 x1, 其次 x；優先找 y1, 其次 y2, 其次 y
        default_x = next((c for c in all_cols if c.lower() == 'x1'), 
                         next((c for c in all_cols if c.lower() == 'x'), all_cols[1] if len(all_cols)>1 else all_cols[0]))
        
        default_y = next((c for c in all_cols if c.lower() == 'y1'), 
                         next((c for c in all_cols if c.lower() == 'y2'), 
                         next((c for c in all_cols if c.lower() == 'y'), all_cols[2] if len(all_cols)>2 else all_cols[0])))

        x_col = st.sidebar.selectbox("選擇用於排序的 X 座標", all_cols, index=all_cols.index(default_x))
        y_col = st.sidebar.selectbox("選擇用於排序的 Y 座標", all_cols, index=all_cols.index(default_y))
        
        # --- 處理邏輯 ---
        
        # 1. 計算角度
        # 使用 numpy 的 arctan2 計算角度 (radians)
        # arctan2(y, x) 回傳值範圍為 -pi 到 pi
        theta = np.arctan2(df[y_col], df[x_col])
        df['_theta'] = theta
        
        # 2. 順時針排序
        # 角度由大到小排列 (pi -> 0 -> -pi) 即為順時針
        df_sorted = df.sort_values(by='_theta', ascending=False).reset_index(drop=True)
        
        # 3. 尋找新起點 (第三象限最靠近 Y 軸)
        # 第三象限: x < 0, y < 0
        q3_mask = (df_sorted[x_col] < 0) & (df_sorted[y_col] < 0)
        q3_points = df_sorted[q3_mask]
        
        msg_area = st.empty()
        
        if q3_points.empty:
            st.warning("⚠️ 警告：資料中沒有位於第三象限 (x<0, y<0) 的點。維持順時針排序，但起點可能未調整。")
            start_index = 0
        else:
            # 找 x 值最大 (因為是負數，越接近 0 值越大)
            target_idx_in_q3 = q3_points[x_col].idxmax()
            start_index = target_idx_in_q3
            
        # 4. Shift 資料 (重新切分並接合)
        df_final = pd.concat([
            df_sorted.iloc[start_index:],
            df_sorted.iloc[:start_index]
        ]).reset_index(drop=True)
        
        # 移除暫存的角度欄位
        df_final.drop(columns=['_theta'], inplace=True)
        
        # --- 顯示結果 ---
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("📊 排序後數據預覽")
            st.dataframe(df_final.head(10))
            st.caption(f"共 {len(df_final)} 筆資料，起點設為原始資料的 index: {start_index}")

        with col2:
            st.subheader("📈 形狀預覽")
            # 標記起點以便視覺確認
            df_final['Type'] = 'Other Points'
            df_final.loc[0, 'Type'] = 'Start Point (New Node 1)'
            
            fig = px.scatter(df_final, x=x_col, y=y_col, color='Type', 
                             color_discrete_map={'Start Point (New Node 1)': 'red', 'Other Points': 'blue'},
                             hover_data=df_final.columns)
            
            # 設定等比例顯示，避免圖形變形
            fig.update_yaxes(scaleanchor="x", scaleratio=1)
            # 加入連線以確認順序
            fig.add_traces(px.line(df_final, x=x_col, y=y_col).data[0])
            st.plotly_chart(fig, use_container_width=True)

        # --- 下載區 ---
        st.subheader("📥 下載結果")
        
        # 轉換為 CSV 字串
        csv = df_final.to_csv(index=False).encode('utf-8')
        
        # 轉換為 TXT (Tab 分隔) 字串
        txt = df_final.to_csv(index=False, sep='\t').encode('utf-8')
        
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                label="下載為 CSV 檔",
                data=csv,
                file_name="sorted_tunnel_data.csv",
                mime="text/csv",
            )
        with c2:
            st.download_button(
                label="下載為 TXT 檔 (Tab分隔)",
                data=txt,
                file_name="sorted_tunnel_data.txt",
                mime="text/plain",
            )

    except Exception as e:
        st.error(f"處理檔案時發生錯誤：{e}")
        st.info("請確認上傳的檔案是否為有效的 CSV/TXT 格式，且包含座標欄位。")

else:
    st.info("👈 請從左側選單上傳檔案以開始使用。")