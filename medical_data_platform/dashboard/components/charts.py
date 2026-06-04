"""
MedInsight Dashboard - Reusable Chart Components
"""

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


DARK_TEMPLATE = "plotly_dark"
PRIMARY_COLOR = "#d63031"
COLOR_PALETTE = [
    "#d63031",  # Medical red
    "#00d4aa",  # Teal
    "#74b9ff",  # Blue
    "#f9ca24",  # Gold
    "#a29bfe",  # Lavender
    "#00b894",  # Green
    "#fd79a8",  # Pink
    "#fdcb6e",  # Orange-yellow
    "#55efc4",  # Mint
    "#e17055",  # Coral
]


def apply_dark_layout(fig: go.Figure, title: str = "", height: int = 400) -> go.Figure:
    fig.update_layout(
        template=DARK_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        title=dict(text=title, font=dict(size=14, color="#e8edf3", family="system-ui")),
        font=dict(color="#7d8da8", family="system-ui"),
        margin=dict(l=10, r=10, t=45, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(255,255,255,0.07)"),
        hoverlabel=dict(
            bgcolor="rgba(11,18,33,0.95)",
            bordercolor="rgba(214,48,49,0.5)",
            font=dict(color="#e8edf3"),
        ),
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)", linecolor="rgba(255,255,255,0.06)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)", linecolor="rgba(255,255,255,0.06)")
    return fig


def line_chart(
    df: pd.DataFrame, x: str, y: str | list[str],
    title: str = "", color: str | None = None, height: int = 400
) -> go.Figure:
    fig = px.line(
        df, x=x, y=y, color=color, title=title,
        color_discrete_sequence=COLOR_PALETTE,
        markers=True,
    )
    return apply_dark_layout(fig, title, height)


def bar_chart(
    df: pd.DataFrame, x: str, y: str,
    title: str = "", color: str | None = None,
    orientation: str = "v", height: int = 400
) -> go.Figure:
    fig = px.bar(
        df, x=x, y=y, color=color, title=title,
        orientation=orientation,
        color_discrete_sequence=COLOR_PALETTE,
    )
    return apply_dark_layout(fig, title, height)


def pie_chart(
    df: pd.DataFrame, values: str, names: str,
    title: str = "", height: int = 400
) -> go.Figure:
    fig = px.pie(
        df, values=values, names=names, title=title,
        color_discrete_sequence=COLOR_PALETTE,
        hole=0.4,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return apply_dark_layout(fig, title, height)


def heatmap(
    pivot_df: pd.DataFrame, title: str = "", height: int = 400
) -> go.Figure:
    fig = go.Figure(go.Heatmap(
        z=pivot_df.values,
        x=pivot_df.columns.tolist(),
        y=pivot_df.index.tolist(),
        colorscale=[[0, "#060c16"], [0.35, "#6c1a1c"], [0.65, "#d63031"], [1, "#ff7675"]],
        showscale=True,
    ))
    return apply_dark_layout(fig, title, height)


def scatter_chart(
    df: pd.DataFrame, x: str, y: str, color: str | None = None,
    size: str | None = None, hover_data: list | None = None,
    title: str = "", height: int = 400
) -> go.Figure:
    fig = px.scatter(
        df, x=x, y=y, color=color, size=size,
        hover_data=hover_data, title=title,
        color_discrete_sequence=COLOR_PALETTE,
    )
    return apply_dark_layout(fig, title, height)


def area_chart(
    df: pd.DataFrame, x: str, y: str | list[str],
    title: str = "", height: int = 400
) -> go.Figure:
    fig = px.area(
        df, x=x, y=y, title=title,
        color_discrete_sequence=COLOR_PALETTE,
    )
    return apply_dark_layout(fig, title, height)


def gauge_chart(value: float, max_val: float, title: str = "", height: int = 250) -> go.Figure:
    pct = value / max_val if max_val > 0 else 0
    color = "#3fb950" if pct >= 0.75 else "#d29922" if pct >= 0.50 else "#f85149"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"color": "#e6edf3"}},
        gauge={
            "axis": {"range": [0, max_val], "tickcolor": "#8b949e"},
            "bar": {"color": color},
            "bgcolor": "#161b22",
            "bordercolor": "#30363d",
            "steps": [
                {"range": [0, max_val * 0.5], "color": "#1c2128"},
                {"range": [max_val * 0.5, max_val * 0.75], "color": "#1c2128"},
            ],
        },
        number={"font": {"color": "#e6edf3"}},
    ))
    apply_dark_layout(fig, height=height)
    return fig


def waterfall_chart(
    labels: list[str], values: list[float], title: str = "", height: int = 400
) -> go.Figure:
    measures = ["absolute"] + ["relative"] * (len(values) - 2) + ["total"]
    fig = go.Figure(go.Waterfall(
        x=labels,
        y=values,
        measure=measures,
        connector={"line": {"color": "#30363d"}},
        increasing={"marker": {"color": "#3fb950"}},
        decreasing={"marker": {"color": "#f85149"}},
        totals={"marker": {"color": "#00d4aa"}},
    ))
    return apply_dark_layout(fig, title, height)
