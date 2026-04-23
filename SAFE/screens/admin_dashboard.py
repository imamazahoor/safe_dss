"""
SAFE — Admin / Population Health Dashboard
-------------------------------------------
Read-only aggregate view for administrators. No patient-level filters
are applied, and per-chart small-cell suppression (n<3) protects
anonymity in small cohorts.
"""

import streamlit as st
import plotly.graph_objects as go
from config.theme import COLORS, RADIUS
from components import top_bar
from services.data_service import (
    get_population_kpis,
    get_tier_distribution,
    get_tier_by_age,
    get_tier_by_unit,
    get_alert_response_distribution,
    SUPPRESSION_THRESHOLD,
)


# ============================================================
# CSS
# ============================================================
def _inject_css():
    st.markdown(
        f"""
        <style>
          .admin-header {{
              margin: 0 0 1.5rem 0;
          }}
          .admin-header h2 {{
              margin: 0;
              color: {COLORS['navy_deep']};
              font-size: 1.5rem;
              font-weight: 600;
          }}
          .admin-header p {{
              margin: 0.2rem 0 0 0;
              color: {COLORS['ink_soft']};
              font-size: 0.9rem;
          }}

          /* Privacy caption under the header */
          .privacy-note {{
              background: {COLORS['cream_dark']};
              border-left: 3px solid {COLORS['gold']};
              padding: 0.6rem 0.9rem;
              border-radius: {RADIUS['sm']};
              font-size: 0.8rem;
              color: {COLORS['ink_soft']};
              margin: 0.75rem 0 1.5rem 0;
          }}
          .privacy-note strong {{ color: {COLORS['navy_deep']}; }}

          /* KPI cards — reuse same pattern as clinician dashboard */
          .kpi-card {{
              background: #FFFFFF;
              border: 1px solid {COLORS['beige']};
              border-radius: {RADIUS['md']};
              padding: 1.1rem 1.3rem;
              box-shadow: 0 1px 3px rgba(27, 42, 78, 0.04);
              height: 100%;
          }}
          .kpi-card .label {{
              font-size: 0.78rem;
              color: {COLORS['ink_soft']};
              text-transform: uppercase;
              letter-spacing: 0.05em;
              margin: 0 0 0.4rem 0;
          }}
          .kpi-card .value {{
              font-size: 2rem;
              font-weight: 700;
              color: {COLORS['navy_deep']};
              line-height: 1;
              margin: 0;
          }}
          .kpi-card .hint {{
              font-size: 0.75rem;
              color: {COLORS['ink_light']};
              margin: 0.4rem 0 0 0;
          }}
          .kpi-card.accent-high .value {{ color: {COLORS['risk_high']}; }}
          .kpi-card.accent-gold .value {{ color: {COLORS['gold']}; }}
          .kpi-card.accent-green .value {{ color: {COLORS['risk_low']}; }}

          /* Chart cards */
          .chart-card {{
              background: #FFFFFF;
              border: 1px solid {COLORS['beige']};
              border-radius: {RADIUS['md']};
              padding: 1rem 1.25rem 0.5rem 1.25rem;
              box-shadow: 0 1px 3px rgba(27, 42, 78, 0.04);
              margin-bottom: 1rem;
              height: 100%;
          }}
          .chart-card h3 {{
              margin: 0 0 0.75rem 0;
              color: {COLORS['navy_deep']};
              font-size: 1rem;
              font-weight: 600;
          }}

          /* Suppression placeholder */
          .chart-suppressed {{
              background: {COLORS['cream_dark']};
              border: 1px dashed {COLORS['beige']};
              border-radius: {RADIUS['md']};
              padding: 2.5rem 1.5rem;
              text-align: center;
              color: {COLORS['ink_soft']};
              font-size: 0.9rem;
              margin: 0.5rem 0 1rem 0;
          }}
          .chart-suppressed .icon {{
              font-size: 1.5rem;
              margin-bottom: 0.5rem;
              display: block;
          }}
          .chart-suppressed strong {{ color: {COLORS['navy_deep']}; }}

          /* Footer */
          .admin-footer {{
              margin-top: 2rem;
              padding: 1rem 0;
              border-top: 1px solid {COLORS['beige']};
              font-size: 0.75rem;
              color: {COLORS['ink_soft']};
              font-style: italic;
              text-align: center;
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# TIER COLOR MAP — must match clinician dashboard for consistency
# ============================================================
def _tier_colors(tiers: list[str]) -> list[str]:
    m = {
        "High":     COLORS["risk_high"],
        "Moderate": COLORS["risk_moderate"],
        "Low":      COLORS["risk_low"],
    }
    return [m[t] for t in tiers]


# ============================================================
# SUPPRESSION PLACEHOLDER
# ============================================================
def _render_suppression_placeholder(reason: str):
    st.markdown(
        f"""
        <div class="chart-suppressed">
          <span class="icon">🔒</span>
          <strong>Insufficient data for anonymized display</strong><br/>
          <span>{reason}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# KPI STRIP
# ============================================================
def _render_kpis():
    k = get_population_kpis()

    c1, c2, c3, c4 = st.columns(4, gap="medium")
    with c1:
        st.markdown(
            f"""
            <div class="kpi-card">
              <p class="label">Total patients</p>
              <p class="value">{k['total_patients']}</p>
              <p class="hint">Currently admitted</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="kpi-card accent-high">
              <p class="label">High-risk patients</p>
              <p class="value">{k['high_risk_count']}</p>
              <p class="hint">{k['high_risk_pct']}% of cohort</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""
            <div class="kpi-card accent-gold">
              <p class="label">Avg risk score</p>
              <p class="value">{k['avg_risk_score']:.2f}</p>
              <p class="hint">Across all patients</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c4:
        # Alert response rate — tells the structured-override story
        if k['response_denominator'] == 0:
            value_display = "—"
            hint_display = "No high-risk alerts in cohort"
        else:
            value_display = f"{k['response_rate_pct']:.0f}%"
            hint_display = (f"{k['response_numerator']} of "
                            f"{k['response_denominator']} alerts actioned")
        st.markdown(
            f"""
            <div class="kpi-card accent-green">
              <p class="label">Alert response rate</p>
              <p class="value">{value_display}</p>
              <p class="hint">{hint_display}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# CHART 1 — Tier distribution (donut)
# ============================================================
def _render_tier_donut():
    st.markdown(
        '<div class="chart-card"><h3>Risk tier distribution</h3>',
        unsafe_allow_html=True,
    )
    data = get_tier_distribution()

    if data["suppressed"]:
        _render_suppression_placeholder(data["reason"])
    else:
        fig = go.Figure(data=[go.Pie(
            labels=data["tiers"],
            values=data["counts"],
            hole=0.55,
            marker=dict(colors=_tier_colors(data["tiers"]),
                        line=dict(color="#FFFFFF", width=2)),
            textinfo="label+percent",
            textfont=dict(size=13, color="#FFFFFF"),
            hovertemplate="<b>%{label}</b><br>%{value} patients (%{percent})"
                          "<extra></extra>",
        )])
        fig.update_layout(
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.15,
                        xanchor="center", x=0.5,
                        font=dict(color=COLORS["ink"], size=11)),
            margin=dict(l=10, r=10, t=10, b=30),
            height=290,
            annotations=[dict(
                text=f"<b>{data['total']}</b><br><span style='font-size:11px'>total</span>",
                x=0.5, y=0.5, font=dict(size=18, color=COLORS["navy_deep"]),
                showarrow=False,
            )],
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# CHART 2 — Tier by age (stacked bar)
# ============================================================
def _render_tier_by_age():
    st.markdown(
        '<div class="chart-card"><h3>Risk tier by age group</h3>',
        unsafe_allow_html=True,
    )
    data = get_tier_by_age()

    # If ALL bins are suppressed, show one big placeholder
    all_zero = all(sum(row) == 0 for row in data["matrix"])
    if all_zero:
        _render_suppression_placeholder(
            f"All age bins have fewer than {SUPPRESSION_THRESHOLD} patients."
        )
    else:
        fig = go.Figure()
        for i, tier in enumerate(data["tiers"]):
            fig.add_trace(go.Bar(
                name=tier,
                x=data["age_bins"],
                y=[row[i] for row in data["matrix"]],
                marker_color=_tier_colors([tier])[0],
                hovertemplate=f"<b>%{{x}}</b><br>{tier}: %{{y}} patients<extra></extra>",
            ))

        fig.update_layout(
            barmode="stack",
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            xaxis=dict(title="Age group", gridcolor=COLORS["cream_dark"]),
            yaxis=dict(title="Patients", gridcolor=COLORS["cream_dark"],
                       rangemode="tozero"),
            legend=dict(orientation="h", yanchor="bottom", y=-0.3,
                        xanchor="center", x=0.5,
                        font=dict(color=COLORS["ink"], size=11)),
            margin=dict(l=10, r=10, t=10, b=50),
            height=290,
        )
        st.plotly_chart(fig, use_container_width=True)

        if data["suppressed_bins"]:
            st.caption(
                f"🔒 Bins suppressed for privacy: "
                f"{', '.join(data['suppressed_bins'])} "
                f"(n<{SUPPRESSION_THRESHOLD} each)"
            )

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# CHART 3 — Tier by ICU unit (horizontal stacked bar)
# ============================================================
def _render_tier_by_unit():
    st.markdown(
        '<div class="chart-card"><h3>Risk tier by ICU unit</h3>',
        unsafe_allow_html=True,
    )
    data = get_tier_by_unit()

    all_zero = all(sum(row) == 0 for row in data["matrix"])
    if all_zero:
        _render_suppression_placeholder(
            f"All units have fewer than {SUPPRESSION_THRESHOLD} patients."
        )
    else:
        fig = go.Figure()
        for i, tier in enumerate(data["tiers"]):
            fig.add_trace(go.Bar(
                name=tier,
                y=data["units"],
                x=[row[i] for row in data["matrix"]],
                orientation="h",
                marker_color=_tier_colors([tier])[0],
                hovertemplate=f"<b>%{{y}}</b><br>{tier}: %{{x}} patients<extra></extra>",
            ))

        fig.update_layout(
            barmode="stack",
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            xaxis=dict(title="Patients", gridcolor=COLORS["cream_dark"],
                       rangemode="tozero"),
            yaxis=dict(title="", gridcolor=COLORS["cream_dark"],
                       autorange="reversed"),
            legend=dict(orientation="h", yanchor="bottom", y=-0.3,
                        xanchor="center", x=0.5,
                        font=dict(color=COLORS["ink"], size=11)),
            margin=dict(l=10, r=10, t=10, b=50),
            height=290,
        )
        st.plotly_chart(fig, use_container_width=True)

        if data["suppressed_units"]:
            st.caption(
                f"🔒 Units suppressed for privacy: "
                f"{', '.join(data['suppressed_units'])} "
                f"(n<{SUPPRESSION_THRESHOLD} each)"
            )

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# CHART 4 — Alert response breakdown (donut)
# ============================================================
def _render_alert_response_donut():
    st.markdown(
        '<div class="chart-card"><h3>Alert response breakdown</h3>',
        unsafe_allow_html=True,
    )
    data = get_alert_response_distribution()

    if data["suppressed"]:
        _render_suppression_placeholder(data["reason"])
    else:
        # Color semantics:
        #   Acknowledged → green (positive response)
        #   Overridden   → gold (informed dismissal, neutral)
        #   Pending      → terracotta (awaiting response, needs attention)
        color_map = {
            "Acknowledged": COLORS["risk_low"],
            "Overridden":   COLORS["gold"],
            "Pending":      COLORS["terracotta"],
        }
        chart_colors = [color_map[c] for c in data["categories"]]

        fig = go.Figure(data=[go.Pie(
            labels=data["categories"],
            values=data["counts"],
            hole=0.55,
            marker=dict(colors=chart_colors,
                        line=dict(color="#FFFFFF", width=2)),
            textinfo="label+percent",
            textfont=dict(size=12, color="#FFFFFF"),
            hovertemplate="<b>%{label}</b><br>%{value} alerts (%{percent})"
                          "<extra></extra>",
        )])
        fig.update_layout(
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.15,
                        xanchor="center", x=0.5,
                        font=dict(color=COLORS["ink"], size=11)),
            margin=dict(l=10, r=10, t=10, b=30),
            height=290,
            annotations=[dict(
                text=f"<b>{data['total']}</b><br>"
                     f"<span style='font-size:11px'>high-risk</span>",
                x=0.5, y=0.5, font=dict(size=18, color=COLORS["navy_deep"]),
                showarrow=False,
            )],
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# MAIN RENDER
# ============================================================
def render(on_signout):
    _inject_css()

    user = st.session_state["user"]
    top_bar.render(user, on_signout)

    # Header
    st.markdown(
        f"""
        <div class="admin-header">
          <h2>Population Health Overview</h2>
          <p>Welcome, {user['name']} · read-only aggregate view</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Privacy notice — tied to HW7 part (g)
    st.markdown(
        f"""
        <div class="privacy-note">
          <strong>Privacy note.</strong> This view intentionally omits
          patient-level filters. Charts with fewer than
          {SUPPRESSION_THRESHOLD} patients per cell are suppressed to
          protect anonymity (small-cell suppression, n&lt;{SUPPRESSION_THRESHOLD}).
        </div>
        """,
        unsafe_allow_html=True,
    )

    # KPI strip
    _render_kpis()

    # Small spacer
    st.markdown("<div style='height:1.25rem;'></div>", unsafe_allow_html=True)

    # 2x2 chart grid
    row1_left, row1_right = st.columns(2, gap="medium")
    with row1_left:
        _render_tier_donut()
    with row1_right:
        _render_tier_by_age()

    row2_left, row2_right = st.columns(2, gap="medium")
    with row2_left:
        _render_tier_by_unit()
    with row2_right:
        _render_alert_response_donut()

    # Footer
    st.markdown(
        f"""
        <div class="admin-footer">
          Values reflect currently-admitted ICU patients.
          Cells with fewer than {SUPPRESSION_THRESHOLD} patients are
          withheld to protect patient privacy.
        </div>
        """,
        unsafe_allow_html=True,
    )