# app.py  — Week 9: Dashboard with Database Query (SQLite + Streamlit)
# ---------------------------------------------------------------
# 功能：
# 1) 確保 log.db 以及 logs 表存在；若沒有而同資料夾有 log.csv，會自動匯入建立
# 2) 從 SQLite 讀取資料，提供 Ping 狀態篩選
# 3) 顯示最近 5 筆紀錄、三張折線圖（CPU / Memory / Disk），與簡單統計
# ---------------------------------------------------------------

import os
import sqlite3
import pandas as pd
import streamlit as st

DB_PATH = "log.db"
CSV_PATH = "log.csv"
TABLE = "logs"

# ---- 共同小工具 -------------------------------------------------

def _open_conn():
    # 用 check_same_thread=False 讓 Streamlit 多執行緒時也能讀
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """把欄位名統一成作業規格：Timestamp, CPU, Memory, Disk, Ping_Status, Ping_ms"""
    wanted = ["Timestamp", "CPU", "Memory", "Disk", "Ping_Status", "Ping_ms"]
    # 先做個不區分大小寫的對照
    lower_map = {c.lower(): c for c in df.columns}
    out = {}
    for w in wanted:
        key = w.lower()
        if key in lower_map:
            out[w] = df[lower_map[key]]
        elif w in df.columns:
            out[w] = df[w]
        else:
            # 若缺欄位，補空值
            out[w] = pd.Series([None] * len(df))
    df2 = pd.DataFrame(out)
    # 轉時間
    if "Timestamp" in df2.columns:
        df2["Timestamp"] = pd.to_datetime(df2["Timestamp"], errors="coerce")
    # 數值欄位轉 float
    for col in ["CPU", "Memory", "Disk", "Ping_ms"]:
        if col in df2.columns:
            df2[col] = pd.to_numeric(df2[col], errors="coerce")
    # Ping_Status 轉字串
    if "Ping_Status" in df2.columns:
        df2["Ping_Status"] = df2["Ping_Status"].astype(str)
    return df2

# ---- DB 準備 ----------------------------------------------------

def ensure_db_and_table():
    """確保 DB 與表存在；若有 log.csv 則匯入成 logs 表，否則建空表。"""
    conn = _open_conn()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (TABLE,))
    exists = cur.fetchone() is not None

    if not exists:
        if os.path.exists(CSV_PATH):
            csv_df = pd.read_csv(CSV_PATH)
            csv_df = _normalize_columns(csv_df)
            # 寫入 SQLite 前把時間轉成 ISO 字串，避免型別混亂
            if "Timestamp" in csv_df.columns:
                csv_df["Timestamp"] = csv_df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
            csv_df.to_sql(TABLE, conn, index=False, if_exists="replace")
            st.info("已從 log.csv 建立 log.db 的 logs 表。")
        else:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    Timestamp   TEXT,
                    CPU         REAL,
                    Memory      REAL,
                    Disk        REAL,
                    Ping_Status TEXT,
                    Ping_ms     REAL
                );
                """
            )
            conn.commit()
            st.warning("找不到 log.csv，已先建立空的 logs 表。請上傳/產生日誌後再重整。")
    conn.close()

def load_all() -> pd.DataFrame:
    """讀出全部資料（依時間排序），並轉回合適型別。"""
    conn = _open_conn()
    try:
        df = pd.read_sql_query(f"SELECT * FROM {TABLE}", conn)
    finally:
        conn.close()

    if df.empty:
        return df

    df = _normalize_columns(df)
    return df.sort_values("Timestamp")

# ---- Streamlit UI ----------------------------------------------

st.set_page_config(page_title="資料中心監控儀表板", layout="wide")
st.title("📊 資料中心監控儀表板")

# 準備資料表
ensure_db_and_table()
df_all = load_all()

if df_all.empty:
    st.info("資料庫目前沒有資料（或剛建立）。請先在 Week 7 的 logger 產生資料，再回到這裡重整頁面。")
    st.stop()

# 側邊欄：Ping 狀態篩選
with st.sidebar:
    st.header("篩選")
    selected = st.selectbox("按 Ping 狀態篩選", ["全部", "UP", "DOWN"], index=0)

df = df_all.copy()
if selected != "全部":
    df = df[df["Ping_Status"] == selected]

st.caption(f"顯示筆數：{len(df)}　（總筆數：{len(df_all)}）")
if "Timestamp" in df.columns and not df.empty:
    earliest = df["Timestamp"].min()
    latest = df["Timestamp"].max()
    st.caption(f"時間範圍：{earliest} 〜 {latest}")

# 最近 5 筆紀錄
st.subheader("最後 5 筆紀錄")
st.dataframe(df.tail(5), use_container_width=True)

# KPI（顯示最新一筆）
if not df.empty:
    latest_row = df.iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CPU（%）", f"{latest_row.get('CPU', float('nan')):.1f}")
    c2.metric("Memory（%）", f"{latest_row.get('Memory', float('nan')):.1f}")
    c3.metric("Disk（%）", f"{latest_row.get('Disk', float('nan')):.1f}")
    c4.metric("Ping (ms)", f"{latest_row.get('Ping_ms', float('nan')):.1f}")

# 三張折線圖
st.subheader("趨勢")
chart_base = df.dropna(subset=["Timestamp"]).set_index("Timestamp")
col1, col2, col3 = st.columns(3)

with col1:
    if "CPU" in chart_base.columns:
        st.caption("CPU 使用率")
        st.line_chart(chart_base["CPU"])
with col2:
    if "Memory" in chart_base.columns:
        st.caption("記憶體使用率")
        st.line_chart(chart_base["Memory"])
with col3:
    if "Disk" in chart_base.columns:
        st.caption("磁碟使用率")
        st.line_chart(chart_base["Disk"])

st.success("儀表板已載入 ✅")
