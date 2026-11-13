import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import psycopg2
import pandas as pd
from datetime import date

st.set_page_config(
    page_title="MOEX Options Dashboard",
    page_icon="📊",
    layout="wide",
)

DB_CONFIG = {
    "host": "localhost",
    "port": 7777,
    "dbname": "postgres",
    "user": "postgres",
    "password": "mysecretpassword",
}


@st.cache_resource
def get_connection():
    return psycopg2.connect(**DB_CONFIG)


@st.cache_data(ttl=300)
def load_data(query: str) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(query, conn)
    except Exception:
        conn.reset()
        return pd.read_sql(query, conn)


# ── Sidebar ──────────────────────────────────────────────────

st.sidebar.title("MOEX Options")
page = st.sidebar.radio(
    "Раздел",
    [
        "Опционная доска",
        "Кривая волатильности",
        "IV по сериям",
        "Историческая волатильность",
    ],
)

# ═══════════════════════════════════════════════════════════════
#  1. ОПЦИОННАЯ ДОСКА  (option_std)
# ═══════════════════════════════════════════════════════════════
if page == "Опционная доска":
    st.title("Опционная доска")

    df = load_data("SELECT * FROM option_std ORDER BY today DESC, asset_code, optionseries_code, strike")

    if df.empty:
        st.warning("Нет данных в таблице option_std.")
        st.stop()

    dates = sorted(df["today"].unique(), reverse=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        sel_date = st.selectbox("Дата", dates, index=0)
    df_day = df[df["today"] == sel_date]
    with col2:
        assets = sorted(df_day["asset_code"].unique())
        sel_asset = st.selectbox("Актив", assets)
    df_asset = df_day[df_day["asset_code"] == sel_asset]
    with col3:
        series_list = sorted(df_asset["optionseries_code"].unique())
        sel_series = st.selectbox("Серия", series_list)

    df_series = df_asset[df_asset["optionseries_code"] == sel_series].sort_values("strike")

    if df_series.empty:
        st.info("Нет данных для выбранных фильтров.")
        st.stop()

    central = df_series["central_strike"].iloc[0]

    # ── Улыбка волатильности ──
    fig_smile = go.Figure()
    fig_smile.add_trace(go.Scatter(
        x=df_series["strike"], y=df_series["volatility"],
        mode="lines+markers", name="IV",
        line=dict(color="#636EFA", width=2),
    ))
    fig_smile.add_vline(x=float(central), line_dash="dash", line_color="red",
                        annotation_text=f"Central {central}")
    fig_smile.update_layout(
        title=f"Улыбка волатильности — {sel_asset} / {sel_series}",
        xaxis_title="Strike", yaxis_title="IV, %",
        height=450,
    )
    st.plotly_chart(fig_smile, use_container_width=True)

    # ── Греки ──
    st.subheader("Греки")
    greek_tabs = st.tabs(["Delta", "Gamma", "Vega", "Theta"])

    greeks = [
        ("Delta", "call_delta", "put_delta"),
        ("Gamma", "call_gamma", "put_gamma"),
        ("Vega", "call_vega", "put_vega"),
        ("Theta", "call_theta", "put_theta"),
    ]

    for tab, (name, call_col, put_col) in zip(greek_tabs, greeks):
        with tab:
            fig_g = go.Figure()
            fig_g.add_trace(go.Scatter(
                x=df_series["strike"], y=df_series[call_col],
                mode="lines+markers", name=f"Call {name}",
                line=dict(color="#00CC96"),
            ))
            fig_g.add_trace(go.Scatter(
                x=df_series["strike"], y=df_series[put_col],
                mode="lines+markers", name=f"Put {name}",
                line=dict(color="#EF553B"),
            ))
            fig_g.add_vline(x=float(central), line_dash="dash", line_color="gray")
            fig_g.update_layout(
                xaxis_title="Strike", yaxis_title=name,
                height=380, legend=dict(orientation="h"),
            )
            st.plotly_chart(fig_g, use_container_width=True)

    # ── Offer / Bid ──
    st.subheader("Offer / Bid")
    col_left, col_right = st.columns(2)

    with col_left:
        fig_call = go.Figure()
        fig_call.add_trace(go.Bar(x=df_series["strike"], y=df_series["call_offer"],
                                  name="Call Offer", marker_color="#636EFA"))
        fig_call.add_trace(go.Bar(x=df_series["strike"], y=df_series["call_bid"],
                                  name="Call Bid", marker_color="#00CC96"))
        fig_call.update_layout(title="Call — Offer vs Bid", barmode="group",
                               xaxis_title="Strike", height=350)
        st.plotly_chart(fig_call, use_container_width=True)

    with col_right:
        fig_put = go.Figure()
        fig_put.add_trace(go.Bar(x=df_series["strike"], y=df_series["put_offer"],
                                 name="Put Offer", marker_color="#AB63FA"))
        fig_put.add_trace(go.Bar(x=df_series["strike"], y=df_series["put_bid"],
                                 name="Put Bid", marker_color="#FFA15A"))
        fig_put.update_layout(title="Put — Offer vs Bid", barmode="group",
                              xaxis_title="Strike", height=350)
        st.plotly_chart(fig_put, use_container_width=True)

    # ── Таблица ──
    with st.expander("Показать таблицу данных"):
        st.dataframe(df_series, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
#  2. КРИВАЯ ВОЛАТИЛЬНОСТИ  (volatility_curve)
# ═══════════════════════════════════════════════════════════════
elif page == "Кривая волатильности":
    st.title("Кривая волатильности")

    df = load_data("SELECT * FROM volatility_curve ORDER BY today DESC, asset_code, optionseries_code, strike")

    if df.empty:
        st.warning("Нет данных в таблице volatility_curve.")
        st.stop()

    dates = sorted(df["today"].unique(), reverse=True)
    col1, col2 = st.columns(2)
    with col1:
        sel_date = st.selectbox("Дата", dates, index=0, key="vc_date")
    df_day = df[df["today"] == sel_date]
    with col2:
        assets = sorted(df_day["asset_code"].unique())
        sel_asset = st.selectbox("Актив", assets, key="vc_asset")
    df_asset = df_day[df_day["asset_code"] == sel_asset]

    series_types = sorted(df_asset["series_type"].unique())
    sel_types = st.multiselect("Тип серии", series_types, default=series_types, key="vc_types")
    df_filtered = df_asset[df_asset["series_type"].isin(sel_types)]

    # ── Все серии на одном графике ──
    fig = px.line(
        df_filtered.sort_values("strike"),
        x="strike", y="volatility",
        color="optionseries_code",
        title=f"Кривые волатильности — {sel_asset} ({sel_date})",
        labels={"strike": "Strike", "volatility": "IV, %", "optionseries_code": "Серия"},
    )
    fig.update_layout(height=550, legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, use_container_width=True)

    # ── Сравнение серий по дате экспирации ──
    st.subheader("Сравнение IV по экспирациям")
    series_info = (
        df_filtered.groupby(["optionseries_code", "expiration_date", "central_strike"])
        .agg(iv_at_central=("volatility", "first"), points=("strike", "count"))
        .reset_index()
        .sort_values("expiration_date")
    )
    st.dataframe(series_info, use_container_width=True, hide_index=True)

    with st.expander("Показать все данные"):
        st.dataframe(df_filtered, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
#  3. IV ПО СЕРИЯМ  (option_volatility / option_volatility_plus)
# ═══════════════════════════════════════════════════════════════
elif page == "IV по сериям":
    st.title("Подразумеваемая волатильность по сериям")

    source = st.radio("Источник", ["option_volatility", "option_volatility_plus"], horizontal=True)
    df = load_data(f"SELECT * FROM {source} ORDER BY today DESC, asset_code, expiration_date")

    if df.empty:
        st.warning(f"Нет данных в таблице {source}.")
        st.stop()

    dates = sorted(df["today"].unique(), reverse=True)
    col1, col2 = st.columns(2)
    with col1:
        sel_date = st.selectbox("Дата", dates, index=0, key="iv_date")
    df_day = df[df["today"] == sel_date]
    with col2:
        assets = sorted(df_day["asset_code"].unique())
        sel_asset = st.selectbox("Актив", assets, key="iv_asset")
    df_asset = df_day[df_day["asset_code"] == sel_asset].sort_values("expiration_date")

    # ── Структура волатильности по срокам ──
    fig_term = go.Figure()
    fig_term.add_trace(go.Bar(
        x=df_asset["expiration_date"].astype(str),
        y=df_asset["volatility"],
        text=df_asset["volatility"].round(2),
        textposition="outside",
        marker_color="#636EFA",
    ))
    fig_term.update_layout(
        title=f"Временная структура IV — {sel_asset} ({sel_date})",
        xaxis_title="Дата экспирации",
        yaxis_title="IV, %",
        height=450,
    )
    st.plotly_chart(fig_term, use_container_width=True)

    # ── Exp STD (если plus) ──
    if source == "option_volatility_plus" and "exp_std" in df_asset.columns:
        st.subheader("Expected Straddle (EXP STD)")
        fig_std = go.Figure()
        fig_std.add_trace(go.Bar(
            x=df_asset["expiration_date"].astype(str),
            y=df_asset["exp_std"],
            text=df_asset["exp_std"].round(2),
            textposition="outside",
            marker_color="#00CC96",
        ))
        fig_std.update_layout(
            title=f"EXP STD — {sel_asset}",
            xaxis_title="Дата экспирации",
            yaxis_title="EXP STD",
            height=400,
        )
        st.plotly_chart(fig_std, use_container_width=True)

    # ── Историческая динамика IV ──
    if len(dates) > 1:
        st.subheader("Динамика IV во времени")
        df_hist = df[df["asset_code"] == sel_asset].sort_values("today")
        fig_hist = px.line(
            df_hist, x="today", y="volatility",
            color="optionseries_code",
            title=f"IV по дням — {sel_asset}",
            labels={"today": "Дата", "volatility": "IV, %"},
        )
        fig_hist.update_layout(height=400, legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig_hist, use_container_width=True)

    with st.expander("Показать таблицу"):
        st.dataframe(df_asset, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
#  4. ИСТОРИЧЕСКАЯ ВОЛАТИЛЬНОСТЬ  (market_history)
# ═══════════════════════════════════════════════════════════════
elif page == "Историческая волатильность":
    st.title("Историческая волатильность (HV)")

    df = load_data("SELECT * FROM market_history ORDER BY tradedate DESC, asset")

    if df.empty:
        st.warning("Нет данных в таблице market_history.")
        st.stop()

    assets = sorted(df["asset"].unique())
    sel_asset = st.selectbox("Актив", assets, key="hv_asset")
    df_asset = df[df["asset"] == sel_asset].sort_values("tradedate")

    min_date = df_asset["tradedate"].min()
    max_date = df_asset["tradedate"].max()
    date_range = st.slider(
        "Период",
        min_value=min_date, max_value=max_date,
        value=(min_date, max_date),
        key="hv_range",
    )
    df_period = df_asset[
        (df_asset["tradedate"] >= date_range[0]) &
        (df_asset["tradedate"] <= date_range[1])
    ]

    # ── HV 10 / 20 / 30 ──
    st.subheader("HV 10 / 20 / 30")
    fig_hv = go.Figure()
    colors = {"hv_10": "#636EFA", "hv_20": "#EF553B", "hv_30": "#00CC96"}
    for col, color in colors.items():
        fig_hv.add_trace(go.Scatter(
            x=df_period["tradedate"], y=df_period[col],
            mode="lines", name=col.upper(),
            line=dict(color=color, width=2),
        ))
    fig_hv.update_layout(
        title=f"Историческая волатильность — {sel_asset}",
        xaxis_title="Дата", yaxis_title="HV, %",
        height=450, legend=dict(orientation="h"),
    )
    st.plotly_chart(fig_hv, use_container_width=True)

    # ── Цена (LAST) ──
    st.subheader("Цена закрытия")
    fig_price = go.Figure()
    fig_price.add_trace(go.Scatter(
        x=df_period["tradedate"], y=df_period["last"],
        mode="lines", name="LAST",
        line=dict(color="#AB63FA", width=2),
    ))
    fig_price.update_layout(
        title=f"Цена ближайшего фьючерса — {sel_asset}",
        xaxis_title="Дата", yaxis_title="Цена",
        height=400,
    )
    st.plotly_chart(fig_price, use_container_width=True)

    # ── Объём и ОИ ──
    col_left, col_right = st.columns(2)
    with col_left:
        fig_vol = go.Figure()
        fig_vol.add_trace(go.Bar(
            x=df_period["tradedate"], y=df_period["voltoday"],
            name="Объём", marker_color="#FFA15A",
        ))
        fig_vol.update_layout(title="Объём торгов", xaxis_title="Дата",
                              yaxis_title="Контракты", height=350)
        st.plotly_chart(fig_vol, use_container_width=True)

    with col_right:
        fig_oi = go.Figure()
        fig_oi.add_trace(go.Scatter(
            x=df_period["tradedate"], y=df_period["openposition"],
            mode="lines", name="OI",
            line=dict(color="#19D3F3", width=2),
            fill="tozeroy",
        ))
        fig_oi.update_layout(title="Открытый интерес", xaxis_title="Дата",
                             yaxis_title="Контракты", height=350)
        st.plotly_chart(fig_oi, use_container_width=True)

    # ── OHLC ──
    st.subheader("OHLC")
    fig_ohlc = go.Figure(data=go.Candlestick(
        x=df_period["tradedate"],
        open=df_period["open"],
        high=df_period["high"],
        low=df_period["low"],
        close=df_period["last"],
    ))
    fig_ohlc.update_layout(
        title=f"Свечной график — {sel_asset}",
        xaxis_title="Дата", yaxis_title="Цена",
        height=450, xaxis_rangeslider_visible=False,
    )
    st.plotly_chart(fig_ohlc, use_container_width=True)

    with st.expander("Показать таблицу"):
        st.dataframe(df_period, use_container_width=True, hide_index=True)
