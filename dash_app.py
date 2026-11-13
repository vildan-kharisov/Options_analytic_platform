import dash
from dash import dcc, html, callback, Input, Output, dash_table
import plotly.graph_objects as go
import plotly.express as px
import psycopg2
import pandas as pd

DB_CONFIG = {
    "host": "localhost",
    "port": 7777,
    "dbname": "postgres",
    "user": "postgres",
    "password": "mysecretpassword",
}


def query(sql: str) -> pd.DataFrame:
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        return pd.read_sql(sql, conn)
    finally:
        conn.close()


COLORS = {
    "bg": "#0e1117",
    "card": "#1a1c23",
    "text": "#fafafa",
    "muted": "#8b949e",
    "accent": "#636EFA",
    "green": "#00CC96",
    "red": "#EF553B",
    "orange": "#FFA15A",
    "purple": "#AB63FA",
    "cyan": "#19D3F3",
    "border": "#30363d",
}

PLOT_TEMPLATE = "plotly_dark"
PLOT_LAYOUT = dict(
    paper_bgcolor=COLORS["card"],
    plot_bgcolor=COLORS["card"],
    font_color=COLORS["text"],
    margin=dict(l=50, r=30, t=50, b=40),
)

TAB_STYLE = {
    "backgroundColor": COLORS["card"],
    "color": COLORS["muted"],
    "border": f"1px solid {COLORS['border']}",
    "padding": "12px 20px",
    "fontWeight": "500",
    "fontSize": "14px",
}
TAB_SELECTED_STYLE = {
    **TAB_STYLE,
    "backgroundColor": COLORS["accent"],
    "color": COLORS["text"],
    "borderBottom": f"2px solid {COLORS['accent']}",
}

TABLE_STYLE_HEADER = {
    "backgroundColor": COLORS["card"],
    "color": COLORS["text"],
    "fontWeight": "bold",
    "border": f"1px solid {COLORS['border']}",
    "textAlign": "center",
}
TABLE_STYLE_DATA = {
    "backgroundColor": COLORS["bg"],
    "color": COLORS["text"],
    "border": f"1px solid {COLORS['border']}",
    "textAlign": "center",
}
TABLE_STYLE_CELL = {
    "padding": "8px",
    "fontSize": "13px",
    "minWidth": "60px",
    "maxWidth": "180px",
    "overflow": "hidden",
    "textOverflow": "ellipsis",
}


def make_dropdown(id_, options, value=None, **kwargs):
    return dcc.Dropdown(
        id=id_,
        options=[{"label": o, "value": o} for o in options],
        value=value or (options[0] if options else None),
        clearable=False,
        style={
            "backgroundColor": COLORS["card"],
            "color": COLORS["text"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "6px",
        },
        **kwargs,
    )


def section_title(text):
    return html.H3(text, style={"color": COLORS["text"], "marginTop": "20px", "marginBottom": "10px"})


# ════════════════════════════════════════════════════
#  APP
# ════════════════════════════════════════════════════

app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    title="MOEX Options Dashboard",
)

app.layout = html.Div(
    style={"backgroundColor": COLORS["bg"], "minHeight": "100vh", "padding": "20px", "fontFamily": "Segoe UI, sans-serif"},
    children=[
        html.H1(
            "MOEX Options Dashboard",
            style={"color": COLORS["text"], "textAlign": "center", "marginBottom": "5px"},
        ),
        html.P(
            "Аналитика опционов и фьючерсов Московской Биржи",
            style={"color": COLORS["muted"], "textAlign": "center", "marginBottom": "25px"},
        ),
        dcc.Tabs(
            id="main-tabs",
            value="tab-board",
            children=[
                dcc.Tab(label="Опционная доска", value="tab-board", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="Кривая волатильности", value="tab-curve", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="IV по сериям", value="tab-iv", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="Историческая волатильность", value="tab-hv", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
            ],
            style={"marginBottom": "20px"},
        ),
        html.Div(id="tab-content"),
    ],
)


# ── Router ──

@callback(Output("tab-content", "children"), Input("main-tabs", "value"))
def render_tab(tab):
    if tab == "tab-board":
        return render_board()
    if tab == "tab-curve":
        return render_curve()
    if tab == "tab-iv":
        return render_iv()
    if tab == "tab-hv":
        return render_hv()
    return html.Div()


# ════════════════════════════════════════════════════
#  TAB 1: ОПЦИОННАЯ ДОСКА
# ════════════════════════════════════════════════════

def render_board():
    df = query("SELECT DISTINCT today FROM option_std ORDER BY today DESC")
    dates = df["today"].astype(str).tolist() if not df.empty else []
    return html.Div([
        html.Div([
            html.Div([html.Label("Дата", style={"color": COLORS["muted"]}), make_dropdown("board-date", dates)], style={"flex": "1", "marginRight": "15px"}),
            html.Div([html.Label("Актив", style={"color": COLORS["muted"]}), make_dropdown("board-asset", [])], style={"flex": "1", "marginRight": "15px"}),
            html.Div([html.Label("Серия", style={"color": COLORS["muted"]}), make_dropdown("board-series", [])], style={"flex": "1"}),
        ], style={"display": "flex", "marginBottom": "20px"}),
        dcc.Graph(id="board-smile"),
        section_title("Греки"),
        dcc.Tabs(id="board-greek-tabs", value="delta", children=[
            dcc.Tab(label="Delta", value="delta", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
            dcc.Tab(label="Gamma", value="gamma", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
            dcc.Tab(label="Vega", value="vega", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
            dcc.Tab(label="Theta", value="theta", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
        ]),
        dcc.Graph(id="board-greeks"),
        section_title("Offer / Bid"),
        html.Div([
            dcc.Graph(id="board-call-ob", style={"flex": "1"}),
            dcc.Graph(id="board-put-ob", style={"flex": "1"}),
        ], style={"display": "flex", "gap": "10px"}),
        section_title("Данные"),
        html.Div(id="board-table"),
    ])


@callback(Output("board-asset", "options"), Output("board-asset", "value"),
          Input("board-date", "value"))
def board_update_assets(sel_date):
    if not sel_date:
        return [], None
    df = query(f"SELECT DISTINCT asset_code FROM option_std WHERE today='{sel_date}' ORDER BY asset_code")
    opts = [{"label": v, "value": v} for v in df["asset_code"]]
    return opts, opts[0]["value"] if opts else None


@callback(Output("board-series", "options"), Output("board-series", "value"),
          Input("board-date", "value"), Input("board-asset", "value"))
def board_update_series(sel_date, sel_asset):
    if not sel_date or not sel_asset:
        return [], None
    df = query(f"SELECT DISTINCT optionseries_code FROM option_std WHERE today='{sel_date}' AND asset_code='{sel_asset}' ORDER BY optionseries_code")
    opts = [{"label": v, "value": v} for v in df["optionseries_code"]]
    return opts, opts[0]["value"] if opts else None


@callback(
    Output("board-smile", "figure"),
    Output("board-greeks", "figure"),
    Output("board-call-ob", "figure"),
    Output("board-put-ob", "figure"),
    Output("board-table", "children"),
    Input("board-date", "value"), Input("board-asset", "value"),
    Input("board-series", "value"), Input("board-greek-tabs", "value"),
)
def board_update_charts(sel_date, sel_asset, sel_series, greek):
    empty = go.Figure().update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE)
    if not all([sel_date, sel_asset, sel_series]):
        return empty, empty, empty, empty, html.Div()

    df = query(
        f"SELECT * FROM option_std WHERE today='{sel_date}' AND asset_code='{sel_asset}' "
        f"AND optionseries_code='{sel_series}' ORDER BY strike"
    )
    if df.empty:
        return empty, empty, empty, empty, html.Div()

    central = float(df["central_strike"].iloc[0])

    # Smile
    fig_smile = go.Figure()
    fig_smile.add_trace(go.Scatter(x=df["strike"], y=df["volatility"], mode="lines+markers",
                                   name="IV", line=dict(color=COLORS["accent"], width=2)))
    fig_smile.add_vline(x=central, line_dash="dash", line_color=COLORS["red"],
                        annotation_text=f"Central {central}", annotation_font_color=COLORS["red"])
    fig_smile.update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE,
                            title=f"Улыбка волатильности — {sel_asset} / {sel_series}",
                            xaxis_title="Strike", yaxis_title="IV, %", height=450)

    # Greeks
    call_col = f"call_{greek}"
    put_col = f"put_{greek}"
    fig_g = go.Figure()
    fig_g.add_trace(go.Scatter(x=df["strike"], y=df[call_col], mode="lines+markers",
                               name=f"Call {greek.title()}", line=dict(color=COLORS["green"])))
    fig_g.add_trace(go.Scatter(x=df["strike"], y=df[put_col], mode="lines+markers",
                               name=f"Put {greek.title()}", line=dict(color=COLORS["red"])))
    fig_g.add_vline(x=central, line_dash="dash", line_color=COLORS["muted"])
    fig_g.update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE,
                        xaxis_title="Strike", yaxis_title=greek.title(), height=400,
                        legend=dict(orientation="h", y=-0.15))

    # Call O/B
    fig_call = go.Figure()
    fig_call.add_trace(go.Bar(x=df["strike"], y=df["call_offer"], name="Offer", marker_color=COLORS["accent"]))
    fig_call.add_trace(go.Bar(x=df["strike"], y=df["call_bid"], name="Bid", marker_color=COLORS["green"]))
    fig_call.update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE,
                           title="Call — Offer vs Bid", barmode="group",
                           xaxis_title="Strike", height=360)

    # Put O/B
    fig_put = go.Figure()
    fig_put.add_trace(go.Bar(x=df["strike"], y=df["put_offer"], name="Offer", marker_color=COLORS["purple"]))
    fig_put.add_trace(go.Bar(x=df["strike"], y=df["put_bid"], name="Bid", marker_color=COLORS["orange"]))
    fig_put.update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE,
                          title="Put — Offer vs Bid", barmode="group",
                          xaxis_title="Strike", height=360)

    # Table
    show_cols = ["strike", "volatility", "call_offer", "call_bid", "call_delta", "call_theta",
                 "put_offer", "put_bid", "put_delta", "put_theta"]
    tbl = dash_table.DataTable(
        data=df[show_cols].round(4).to_dict("records"),
        columns=[{"name": c, "id": c} for c in show_cols],
        style_header=TABLE_STYLE_HEADER,
        style_data=TABLE_STYLE_DATA,
        style_cell=TABLE_STYLE_CELL,
        page_size=20,
        style_table={"overflowX": "auto"},
    )
    return fig_smile, fig_g, fig_call, fig_put, tbl


# ════════════════════════════════════════════════════
#  TAB 2: КРИВАЯ ВОЛАТИЛЬНОСТИ
# ════════════════════════════════════════════════════

def render_curve():
    df = query("SELECT DISTINCT today FROM volatility_curve ORDER BY today DESC")
    dates = df["today"].astype(str).tolist() if not df.empty else []
    return html.Div([
        html.Div([
            html.Div([html.Label("Дата", style={"color": COLORS["muted"]}), make_dropdown("curve-date", dates)], style={"flex": "1", "marginRight": "15px"}),
            html.Div([html.Label("Актив", style={"color": COLORS["muted"]}), make_dropdown("curve-asset", [])], style={"flex": "1", "marginRight": "15px"}),
            html.Div([html.Label("Тип серии", style={"color": COLORS["muted"]}),
                       dcc.Checklist(id="curve-types", options=[], value=[], inline=True,
                                     style={"color": COLORS["text"]},
                                     inputStyle={"marginRight": "5px"},
                                     labelStyle={"marginRight": "15px"})],
                     style={"flex": "1"}),
        ], style={"display": "flex", "marginBottom": "20px"}),
        dcc.Graph(id="curve-chart"),
        section_title("Сводка по сериям"),
        html.Div(id="curve-table"),
    ])


@callback(Output("curve-asset", "options"), Output("curve-asset", "value"),
          Input("curve-date", "value"))
def curve_update_assets(sel_date):
    if not sel_date:
        return [], None
    df = query(f"SELECT DISTINCT asset_code FROM volatility_curve WHERE today='{sel_date}' ORDER BY asset_code")
    opts = [{"label": v, "value": v} for v in df["asset_code"]]
    return opts, opts[0]["value"] if opts else None


@callback(Output("curve-types", "options"), Output("curve-types", "value"),
          Input("curve-date", "value"), Input("curve-asset", "value"))
def curve_update_types(sel_date, sel_asset):
    if not sel_date or not sel_asset:
        return [], []
    df = query(f"SELECT DISTINCT series_type FROM volatility_curve WHERE today='{sel_date}' AND asset_code='{sel_asset}' ORDER BY series_type")
    types = df["series_type"].tolist()
    return [{"label": t, "value": t} for t in types], types


@callback(Output("curve-chart", "figure"), Output("curve-table", "children"),
          Input("curve-date", "value"), Input("curve-asset", "value"), Input("curve-types", "value"))
def curve_update(sel_date, sel_asset, sel_types):
    empty = go.Figure().update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE)
    if not sel_date or not sel_asset or not sel_types:
        return empty, html.Div()

    types_str = ",".join(f"'{t}'" for t in sel_types)
    df = query(
        f"SELECT * FROM volatility_curve WHERE today='{sel_date}' AND asset_code='{sel_asset}' "
        f"AND series_type IN ({types_str}) ORDER BY optionseries_code, strike"
    )
    if df.empty:
        return empty, html.Div()

    fig = px.line(df, x="strike", y="volatility", color="optionseries_code",
                  template=PLOT_TEMPLATE,
                  labels={"strike": "Strike", "volatility": "IV, %", "optionseries_code": "Серия"})
    fig.update_layout(**PLOT_LAYOUT, title=f"Кривые волатильности — {sel_asset} ({sel_date})",
                      height=550, legend=dict(orientation="h", y=-0.2))

    summary = (df.groupby(["optionseries_code", "expiration_date", "series_type", "central_strike"])
               .agg(points=("strike", "count"), min_iv=("volatility", "min"), max_iv=("volatility", "max"))
               .reset_index().sort_values("expiration_date"))
    summary = summary.round(2)
    tbl = dash_table.DataTable(
        data=summary.to_dict("records"),
        columns=[{"name": c, "id": c} for c in summary.columns],
        style_header=TABLE_STYLE_HEADER, style_data=TABLE_STYLE_DATA,
        style_cell=TABLE_STYLE_CELL, style_table={"overflowX": "auto"},
    )
    return fig, tbl


# ════════════════════════════════════════════════════
#  TAB 3: IV ПО СЕРИЯМ
# ════════════════════════════════════════════════════

def render_iv():
    df = query("SELECT DISTINCT today FROM option_volatility ORDER BY today DESC")
    dates = df["today"].astype(str).tolist() if not df.empty else []
    return html.Div([
        html.Div([
            html.Div([html.Label("Источник", style={"color": COLORS["muted"]}),
                       make_dropdown("iv-source", ["option_volatility", "option_volatility_plus"])],
                     style={"flex": "1", "marginRight": "15px"}),
            html.Div([html.Label("Дата", style={"color": COLORS["muted"]}), make_dropdown("iv-date", dates)], style={"flex": "1", "marginRight": "15px"}),
            html.Div([html.Label("Актив", style={"color": COLORS["muted"]}), make_dropdown("iv-asset", [])], style={"flex": "1"}),
        ], style={"display": "flex", "marginBottom": "20px"}),
        dcc.Graph(id="iv-term"),
        html.Div(id="iv-std-chart"),
        section_title("Динамика IV"),
        dcc.Graph(id="iv-history"),
        section_title("Данные"),
        html.Div(id="iv-table"),
    ])


@callback(Output("iv-date", "options"), Output("iv-date", "value"),
          Output("iv-asset", "options"), Output("iv-asset", "value"),
          Input("iv-source", "value"))
def iv_update_filters(source):
    if not source:
        return [], None, [], None
    df = query(f"SELECT DISTINCT today FROM {source} ORDER BY today DESC")
    dates = df["today"].astype(str).tolist()
    date_opts = [{"label": d, "value": d} for d in dates]
    sel_date = dates[0] if dates else None

    if sel_date:
        df_a = query(f"SELECT DISTINCT asset_code FROM {source} WHERE today='{sel_date}' ORDER BY asset_code")
        assets = [{"label": v, "value": v} for v in df_a["asset_code"]]
    else:
        assets = []
    return date_opts, sel_date, assets, assets[0]["value"] if assets else None


@callback(
    Output("iv-term", "figure"), Output("iv-std-chart", "children"),
    Output("iv-history", "figure"), Output("iv-table", "children"),
    Input("iv-source", "value"), Input("iv-date", "value"), Input("iv-asset", "value"),
)
def iv_update(source, sel_date, sel_asset):
    empty = go.Figure().update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE)
    if not all([source, sel_date, sel_asset]):
        return empty, html.Div(), empty, html.Div()

    df_day = query(
        f"SELECT * FROM {source} WHERE today='{sel_date}' AND asset_code='{sel_asset}' ORDER BY expiration_date"
    )

    # Term structure
    fig_term = go.Figure()
    if not df_day.empty:
        fig_term.add_trace(go.Bar(
            x=df_day["expiration_date"].astype(str), y=df_day["volatility"],
            text=df_day["volatility"].round(2), textposition="outside",
            marker_color=COLORS["accent"],
        ))
    fig_term.update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE,
                           title=f"Временная структура IV — {sel_asset} ({sel_date})",
                           xaxis_title="Дата экспирации", yaxis_title="IV, %", height=450)

    # EXP STD
    std_div = html.Div()
    if source == "option_volatility_plus" and "exp_std" in df_day.columns and not df_day.empty:
        fig_std = go.Figure()
        fig_std.add_trace(go.Bar(
            x=df_day["expiration_date"].astype(str), y=df_day["exp_std"],
            text=df_day["exp_std"].round(2), textposition="outside",
            marker_color=COLORS["green"],
        ))
        fig_std.update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE,
                              title=f"Expected Straddle — {sel_asset}", height=400,
                              xaxis_title="Дата экспирации", yaxis_title="EXP STD")
        std_div = html.Div([section_title("Expected Straddle"), dcc.Graph(figure=fig_std)])

    # History
    df_all = query(f"SELECT * FROM {source} WHERE asset_code='{sel_asset}' ORDER BY today")
    fig_hist = go.Figure()
    if not df_all.empty:
        fig_hist = px.line(df_all, x="today", y="volatility", color="optionseries_code",
                           template=PLOT_TEMPLATE,
                           labels={"today": "Дата", "volatility": "IV, %"})
    fig_hist.update_layout(**PLOT_LAYOUT, title=f"IV по дням — {sel_asset}",
                           height=400, legend=dict(orientation="h", y=-0.25))

    # Table
    tbl = html.Div()
    if not df_day.empty:
        show = ["optionseries_code", "futures_code", "central_strike", "series_type",
                "volatility", "expiration_date"]
        if "exp_std" in df_day.columns:
            show.insert(5, "exp_std")
        tbl = dash_table.DataTable(
            data=df_day[show].round(4).to_dict("records"),
            columns=[{"name": c, "id": c} for c in show],
            style_header=TABLE_STYLE_HEADER, style_data=TABLE_STYLE_DATA,
            style_cell=TABLE_STYLE_CELL, style_table={"overflowX": "auto"},
        )
    return fig_term, std_div, fig_hist, tbl


# ════════════════════════════════════════════════════
#  TAB 4: ИСТОРИЧЕСКАЯ ВОЛАТИЛЬНОСТЬ
# ════════════════════════════════════════════════════

def render_hv():
    df = query("SELECT DISTINCT asset FROM market_history ORDER BY asset")
    assets = df["asset"].tolist() if not df.empty else []

    df_range = query("SELECT MIN(tradedate) AS mn, MAX(tradedate) AS mx FROM market_history")
    min_d = str(df_range["mn"].iloc[0]) if not df_range.empty and df_range["mn"].iloc[0] else "2020-01-01"
    max_d = str(df_range["mx"].iloc[0]) if not df_range.empty and df_range["mx"].iloc[0] else "2026-12-31"

    return html.Div([
        html.Div([
            html.Div([html.Label("Актив", style={"color": COLORS["muted"]}), make_dropdown("hv-asset", assets)],
                     style={"flex": "1", "marginRight": "15px"}),
            html.Div([html.Label("Период", style={"color": COLORS["muted"]}),
                       dcc.DatePickerRange(id="hv-range", start_date=min_d, end_date=max_d,
                                           display_format="YYYY-MM-DD",
                                           style={"backgroundColor": COLORS["card"]})],
                     style={"flex": "2"}),
        ], style={"display": "flex", "marginBottom": "20px"}),
        dcc.Graph(id="hv-chart"),
        section_title("Цена закрытия"),
        dcc.Graph(id="hv-price"),
        html.Div([
            dcc.Graph(id="hv-volume", style={"flex": "1"}),
            dcc.Graph(id="hv-oi", style={"flex": "1"}),
        ], style={"display": "flex", "gap": "10px"}),
        section_title("OHLC"),
        dcc.Graph(id="hv-ohlc"),
        section_title("Данные"),
        html.Div(id="hv-table"),
    ])


@callback(
    Output("hv-chart", "figure"), Output("hv-price", "figure"),
    Output("hv-volume", "figure"), Output("hv-oi", "figure"),
    Output("hv-ohlc", "figure"), Output("hv-table", "children"),
    Input("hv-asset", "value"), Input("hv-range", "start_date"), Input("hv-range", "end_date"),
)
def hv_update(sel_asset, start, end):
    empty = go.Figure().update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE)
    if not sel_asset:
        return empty, empty, empty, empty, empty, html.Div()

    df = query(
        f"SELECT * FROM market_history WHERE asset='{sel_asset}' "
        f"AND tradedate BETWEEN '{start}' AND '{end}' ORDER BY tradedate"
    )
    if df.empty:
        return empty, empty, empty, empty, empty, html.Div("Нет данных")

    # HV
    fig_hv = go.Figure()
    hv_colors = {"hv_10": COLORS["accent"], "hv_20": COLORS["red"], "hv_30": COLORS["green"]}
    for col, color in hv_colors.items():
        fig_hv.add_trace(go.Scatter(x=df["tradedate"], y=df[col], mode="lines",
                                    name=col.upper(), line=dict(color=color, width=2)))
    fig_hv.update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE,
                         title=f"Историческая волатильность — {sel_asset}",
                         xaxis_title="Дата", yaxis_title="HV, %", height=450,
                         legend=dict(orientation="h"))

    # Price
    fig_price = go.Figure()
    fig_price.add_trace(go.Scatter(x=df["tradedate"], y=df["last"], mode="lines",
                                   name="LAST", line=dict(color=COLORS["purple"], width=2)))
    fig_price.update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE,
                            title=f"Цена ближайшего фьючерса — {sel_asset}",
                            xaxis_title="Дата", yaxis_title="Цена", height=400)

    # Volume
    fig_vol = go.Figure()
    fig_vol.add_trace(go.Bar(x=df["tradedate"], y=df["voltoday"], name="Объём",
                             marker_color=COLORS["orange"]))
    fig_vol.update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE,
                          title="Объём торгов", xaxis_title="Дата", yaxis_title="Контракты", height=360)

    # OI
    fig_oi = go.Figure()
    fig_oi.add_trace(go.Scatter(x=df["tradedate"], y=df["openposition"], mode="lines",
                                name="OI", line=dict(color=COLORS["cyan"], width=2), fill="tozeroy"))
    fig_oi.update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE,
                         title="Открытый интерес", xaxis_title="Дата", yaxis_title="Контракты", height=360)

    # OHLC
    fig_ohlc = go.Figure(data=go.Candlestick(
        x=df["tradedate"], open=df["open"], high=df["high"],
        low=df["low"], close=df["last"],
    ))
    fig_ohlc.update_layout(**PLOT_LAYOUT, template=PLOT_TEMPLATE,
                           title=f"Свечной график — {sel_asset}",
                           xaxis_title="Дата", yaxis_title="Цена",
                           height=450, xaxis_rangeslider_visible=False)

    # Table
    show_cols = ["tradedate", "secid", "open", "high", "low", "last",
                 "settleprice", "voltoday", "openposition", "hv_10", "hv_20", "hv_30"]
    tbl = dash_table.DataTable(
        data=df[show_cols].round(2).to_dict("records"),
        columns=[{"name": c, "id": c} for c in show_cols],
        style_header=TABLE_STYLE_HEADER, style_data=TABLE_STYLE_DATA,
        style_cell=TABLE_STYLE_CELL, page_size=20,
        style_table={"overflowX": "auto"},
    )
    return fig_hv, fig_price, fig_vol, fig_oi, fig_ohlc, tbl


# ════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
