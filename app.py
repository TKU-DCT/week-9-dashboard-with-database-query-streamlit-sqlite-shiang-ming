import sqlite3
import pandas as pd
import streamlit as st

# ---------- 基本設定 ----------
st.set_page_config(
    page_title="資料中心監控儀表板（第10週）",
    layout="wide",
)

DB_PATH = "log.db"
TABLE_NAME = "logs"


# ---------- 小工具：找時間欄位 ----------
def find_time_column(df: pd.DataFrame):
    """嘗試從欄位名稱裡找出時間欄位（Timestamp / timestamp / time...）"""
    for col in df.columns:
        if "time" in col.lower():   # 只要欄位名裡有 time
            return col
    return None


# ---------- 資料讀取 ----------
@st.cache_data(ttl=5)
def load_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
        conn.close()

        # 自動找時間欄位
        ts_col = find_time_column(df)
        if ts_col is not None:
            df[ts_col] = pd.to_datetime(df[ts_col])
        return df
    except Exception:
        return None


# ---------- 各頁面 ----------
def page_dashboard(df_all: pd.DataFrame):
    """主儀表板頁面"""
    if df_all is None or df_all.empty:
        st.warning("找不到資料：請先回 Week 7 / 8 產生 log.db（logs 資料表）。")
        return

    # 找時間欄位
    ts_col = find_time_column(df_all)
    if ts_col is None:
        st.error("在資料裡找不到時間欄位（名稱裡要包含 'time'），請檢查 log.db 的欄位名稱。")
        st.write("目前欄位：", list(df_all.columns))
        return

    # ---- Sidebar filter（在 main 裡面用 sidebar 的值）----
    with st.sidebar:
        st.title("導航")
        st.radio("前往", ["儀表板"], index=0, key="nav_dummy")  # 只是佔位

        st.markdown("---")
        st.subheader("控制")

        ping_filter = st.selectbox("依 Ping 狀態過濾", ["全部", "UP", "DOWN"])
        cpu_threshold = st.slider("只標註 CPU 佔比 (%)", 0, 100, 70)

        refresh_clicked = st.button("立即刷新")

    # 立即刷新：清掉 cache 再重跑
    if refresh_clicked:
        load_data.clear()
        st.experimental_rerun()

    # ---- 套用篩選 ----
    df = df_all.copy()

    if ping_filter != "全部" and "Ping_Status" in df.columns:
        df = df[df["Ping_Status"] == ping_filter]

    # ---- 頂部摘要 ----
    min_ts = df_all[ts_col].min()
    max_ts = df_all[ts_col].max()

    st.success(
        f"資料筆數：{len(df_all)}，時間範圍："
        f"{min_ts.strftime('%Y-%m-%d %H:%M:%S')} → {max_ts.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # ---- 三個指標（最新值）----
    latest = df_all.iloc[-1] if not df_all.empty else None

    col1, col2, col3 = st.columns(3)
    with col1:
        if latest is not None and "CPU" in df_all.columns:
            st.metric("最新 CPU (%)", f"{latest['CPU']:.1f}")
    with col2:
        if latest is not None and "Memory" in df_all.columns:
            st.metric("最新 Memory (%)", f"{latest['Memory']:.1f}")
    with col3:
        if latest is not None and "Disk" in df_all.columns:
            st.metric("最新 Disk (%)", f"{latest['Disk']:.1f}")

    st.markdown("---")

    # ---- 折線圖區塊 ----
    df_chart = df.copy().set_index(ts_col)

    chart_cols = [c for c in ["CPU", "Memory", "Disk"] if c in df_chart.columns]

    if chart_cols:
        c1, c2 = st.columns([2, 1])

        with c1:
            st.subheader("CPU / Memory / Disk 趨勢")
            st.line_chart(df_chart[chart_cols])

        with c2:
            if "Ping_Status" in df_chart.columns:
                st.subheader("Ping 狀態統計")
                st.bar_chart(df_chart["Ping_Status"].value_counts())

    st.markdown("---")

    # ---- 資料表（只顯示最後 50 筆）----
    st.subheader("最近 50 筆記錄")

    df_table = df_all.copy()
    df_table[ts_col] = df_table[ts_col].dt.strftime("%Y-%m-%d %H:%M:%S")

    if "CPU" in df_table.columns:
        df_table["High_CPU"] = df_table["CPU"] >= cpu_threshold

    st.dataframe(df_table.tail(50), use_container_width=True)


def page_settings(df_all: pd.DataFrame):
    """設定頁（簡單顯示資料結構）"""
    st.header("設定")

    if df_all is None or df_all.empty:
        st.warning("目前沒有資料，請先產生 log.db。")
        return

    st.subheader("欄位資訊")
    st.write(list(df_all.columns))

    st.subheader("Ping 狀態分布")
    if "Ping_Status" in df_all.columns:
        st.bar_chart(df_all["Ping_Status"].value_counts())
    else:
        st.info("資料中沒有 Ping_Status 欄位。")


def page_about():
    """關於頁"""
    st.header("關於")

    st.markdown(
        """
        這個儀表板使用 **Streamlit + SQLite (`log.db`)**，
        顯示系統監控資料：

        - 折線圖：CPU / Memory / Disk  
        - 監控：Ping 狀態、CPU 門檻  
        - 刷新：按鈕手動重新載入資料  

        此為第 10 週作業版本。
        """
    )


def main():
    df_all = load_data()

    # ---- 左邊真正的導航（這邊只決定頁面）----
    with st.sidebar:
        st.title("導航")
        page = st.radio("前往", ["儀表板", "設定", "關於"], index=0)

    # ---- 根據頁面顯示內容 ----
    if page == "儀表板":
        page_dashboard(df_all)
    elif page == "設定":
        page_settings(df_all)
    else:
        page_about()


if __name__ == "__main__":
    main()
