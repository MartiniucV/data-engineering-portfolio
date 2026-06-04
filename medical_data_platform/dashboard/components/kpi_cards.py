"""
MedInsight Dashboard - Glassmorphism KPI Card Components
"""

import streamlit as st


def _css() -> str:
    from pathlib import Path
    p = Path(__file__).parent.parent / "assets" / "style.css"
    return f"<style>{p.read_text()}</style>" if p.exists() else ""


def kpi_card(
    icon: str,
    label: str,
    value: str,
    delta: str | None = None,
    delta_up: bool | None = None,
    accent: str = "red",   # red | teal | gold | blue
) -> str:
    delta_html = ""
    if delta:
        direction = "up" if delta_up else ("down" if delta_up is False else "flat")
        arrow = "↑ " if delta_up else ("↓ " if delta_up is False else "")
        delta_html = f'<div class="kpi-delta {direction}">{arrow}{delta}</div>'

    return f"""
<div class="kpi-card accent-{accent}">
  <span class="kpi-icon">{icon}</span>
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value}</div>
  {delta_html}
</div>"""


def kpi_row(cards: list[str]) -> None:
    """Render cards in a responsive CSS grid."""
    inner = "\n".join(cards)
    st.markdown(f'<div class="kpi-grid">{inner}</div>', unsafe_allow_html=True)


def section_header(title: str, icon: str = "") -> None:
    prefix = f"{icon} " if icon else ""
    st.markdown(
        f'<div class="section-title">{prefix}{title}</div>',
        unsafe_allow_html=True,
    )


def brand_header(subtitle: str = "Enterprise Healthcare Analytics") -> None:
    st.markdown(f"""
<div class="brand-header">
  <div class="brand-cross">🏥</div>
  <div class="brand-text">
    <div class="brand-title">MedInsight Analytics</div>
    <div class="brand-sub">{subtitle}</div>
  </div>
  <div style="margin-left:auto;font-size:0.72rem;color:#3d4f69;">
    <span class="live-dot"></span>Live
  </div>
</div>""", unsafe_allow_html=True)


def insight_banner(text: str, accent: str = "red") -> None:
    icon = "⚠️" if accent == "red" else "💡"
    st.markdown(
        f'<div class="insight-banner {accent}">{icon} {text}</div>',
        unsafe_allow_html=True,
    )
