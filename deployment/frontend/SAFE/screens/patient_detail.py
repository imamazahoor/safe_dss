"""
SAFE — Patient Risk Assessment Report
--------------------------------------
Full-screen patient detail view. Navigated to from the dashboard's
📄 View action. Layout:

  1. Patient Header (name, demographics, back button)
  2. Risk Classification Banner (tier, score, confirm/reclassify)
  3. Explanation Panel (key drivers + risk score trend chart)
  4. Preliminary Recommendations Panel
"""
from config.standards import LOINC, SNOMED_RISK_TIER, snomed_tier_ref
import streamlit as st
import plotly.graph_objects as go
from config.theme import COLORS, RADIUS
from services.data_service import (
    get_patient_detail,
    get_risk_explanation,
    get_risk_history,
    get_recommendations,
    confirm_risk_classification,
    reclassify_patient,
)


# ============================================================
# CSS
# ============================================================
def _inject_css():
    st.markdown(
        f"""
        <style>
          /* Back link */
          .back-link-wrap {{
              margin-bottom: 1rem;
          }}

          /* Patient header card */
          .patient-header {{
              background: #FFFFFF;
              border: 1px solid {COLORS['beige']};
              border-radius: {RADIUS['md']};
              padding: 1.25rem 1.5rem;
              margin-bottom: 1.25rem;
              box-shadow: 0 1px 3px rgba(27, 42, 78, 0.04);
          }}
          .patient-header .pid-small {{
              font-family: 'JetBrains Mono', 'Consolas', monospace;
              font-size: 0.8rem;
              color: {COLORS['ink_soft']};
              letter-spacing: 0.02em;
          }}
          .patient-header h1 {{
              margin: 0.2rem 0 0.5rem 0 !important;
              font-size: 1.75rem;
              color: {COLORS['navy_deep']};
          }}
          .patient-header .demographics {{
              font-size: 0.9rem;
              color: {COLORS['ink_soft']};
          }}
          .patient-header .demographics strong {{
              color: {COLORS['ink']};
              font-weight: 600;
          }}

          /* Risk classification banner — color driven by tier class */
          .risk-banner {{
              border-radius: {RADIUS['md']};
              padding: 1.5rem 2rem;
              margin-bottom: 1.5rem;
              display: flex;
              align-items: center;
              gap: 2rem;
          }}
          .risk-banner.tier-high     {{ background: {COLORS['risk_high_bg']};    border-left: 6px solid {COLORS['risk_high']}; }}
          .risk-banner.tier-moderate {{ background: {COLORS['risk_mod_bg']};     border-left: 6px solid {COLORS['risk_moderate']}; }}
          .risk-banner.tier-low      {{ background: {COLORS['risk_low_bg']};     border-left: 6px solid {COLORS['risk_low']}; }}

          .risk-banner .score-big {{
              font-size: 3.2rem;
              font-weight: 700;
              font-family: 'JetBrains Mono', 'Consolas', monospace;
              line-height: 1;
          }}
          .risk-banner.tier-high     .score-big {{ color: {COLORS['risk_high']}; }}
          .risk-banner.tier-moderate .score-big {{ color: {COLORS['risk_moderate']}; }}
          .risk-banner.tier-low      .score-big {{ color: {COLORS['risk_low']}; }}

          .risk-banner .tier-label {{
              font-size: 1.3rem;
              font-weight: 600;
              margin-bottom: 0.2rem;
          }}
          .risk-banner.tier-high     .tier-label {{ color: {COLORS['risk_high']}; }}
          .risk-banner.tier-moderate .tier-label {{ color: {COLORS['risk_moderate']}; }}
          .risk-banner.tier-low      .tier-label {{ color: {COLORS['risk_low']}; }}

          .risk-banner .timestamp {{
              font-size: 0.85rem;
              color: {COLORS['ink_soft']};
          }}

          /* Section headings above panels */
          .section-heading {{
              font-size: 1.1rem;
              font-weight: 600;
              color: {COLORS['navy_deep']};
              margin: 0 0 0.75rem 0;
          }}
          .section-sub {{
              color: {COLORS['ink_soft']};
              font-size: 0.85rem;
              margin: 0 0 1rem 0;
          }}

          /* Explanation panel — driver rows */
          .driver-panel {{
              background: #FFFFFF;
              border: 1px solid {COLORS['beige']};
              border-radius: {RADIUS['md']};
              padding: 1.25rem 1.5rem;
              margin-bottom: 1.5rem;
          }}
          .driver-row {{
              display: flex;
              align-items: center;
              justify-content: space-between;
              padding: 0.6rem 0;
              border-bottom: 1px solid {COLORS['cream_dark']};
          }}
          .driver-row:last-child {{ border-bottom: none; }}
          .driver-row .driver-name {{
              font-weight: 600;
              color: {COLORS['navy_deep']};
              width: 30%;
          }}
          .driver-row .driver-value {{
              font-family: 'JetBrains Mono', 'Consolas', monospace;
              color: {COLORS['ink']};
              width: 25%;
          }}
          .driver-row .driver-status {{
              font-size: 0.85rem;
              width: 25%;
          }}
          .driver-row .driver-status.up   {{ color: {COLORS['risk_high']}; }}
          .driver-row .driver-status.down {{ color: {COLORS['info']}; }}
          .driver-row .driver-contrib {{
              font-family: 'JetBrains Mono', 'Consolas', monospace;
              font-weight: 600;
              color: {COLORS['navy_deep']};
              width: 20%;
              text-align: right;
          }}

          /* Recommendations panel */
          .rec-panel {{
              background: #FFFFFF;
              border: 1px solid {COLORS['beige']};
              border-radius: {RADIUS['md']};
              padding: 1.25rem 1.5rem;
              margin-bottom: 1.5rem;
          }}
          .rec-panel ul {{
              margin: 0;
              padding-left: 1.25rem;
              color: {COLORS['ink']};
          }}
          .rec-panel li {{
              margin-bottom: 0.5rem;
              line-height: 1.4;
          }}
          .rec-disclaimer {{
              margin-top: 1rem;
              padding-top: 0.75rem;
              border-top: 1px solid {COLORS['cream_dark']};
              font-size: 0.8rem;
              color: {COLORS['ink_soft']};
              font-style: italic;
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# SECTIONS
# ============================================================
def _render_back_bar():
    back, _ = st.columns([1, 6])
    with back:
        if st.button("← Back to dashboard", use_container_width=True):
            st.session_state["route"] = "dashboard"
            st.session_state.pop("selected_patient_id", None)
            st.rerun()


def _render_patient_header(patient: dict):
    st.markdown(
        f"""
        <div class="patient-header">
          <div class="pid-small">{patient['patient_id']}</div>
          <h1>{patient['name']}</h1>
          <div class="demographics">
            <strong>{patient['age']}y</strong> · <strong>{patient['gender']}</strong> ·
            ICU hour <strong>{patient['icu_hour']}</strong> ·
            Admitted <strong>{patient['admitted_at']}</strong>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_risk_banner(patient: dict):
    tier = patient["risk_tier"]
    tier_class = f"tier-{tier.lower()}"

    snomed = SNOMED_RISK_TIER.get(tier, {})

    snomed_ref = (
        f'<div style="font-size:0.75rem; color:{COLORS["ink_soft"]}; '
        f'margin-top:0.3rem; font-family:monospace;">'
        f'SNOMED CT · {snomed.get("code", "")} · {snomed.get("display", "")}'
        f'</div>'
    ) if snomed else ""

    st.markdown(
        f"""
        <div class="risk-banner {tier_class}">
          <div class="score-big">{patient['risk_score']:.2f}</div>
          <div>
            <div class="tier-label">{tier} Risk of Sepsis</div>
            <div class="timestamp">Last assessment: within the past hour</div>
            {snomed_ref}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Action buttons — Confirm or Reclassify
    c2, _ = st.columns([1, 3])
    # with c1:
    #     if st.button("✓ Confirm classification", use_container_width=True,
    #                  type="primary", key="confirm_classification"):
    #         confirm_risk_classification(patient["patient_id"],
    #                                     st.session_state["user"]["user_id"])
    #         st.success("Classification confirmed and logged.")
    with c2:
        if st.button("⟳ Reclassify", use_container_width=True,
                     key="open_reclassify"):
            st.session_state["show_reclassify_form"] = True
            st.rerun()

    # Inline reclassify form, shown only when the button is clicked
    if st.session_state.get("show_reclassify_form"):
        with st.container(border=True):
            st.markdown("**Reclassify patient**")
            new_tier = st.selectbox(
                "New risk tier",
                options=["High", "Moderate", "Low"],
                index=["High", "Moderate", "Low"].index(tier),
                key="reclassify_tier",
            )
            reason = st.text_area(
                "Reason for reclassification (required)",
                placeholder="e.g., Patient's fever is from post-op inflammation, not infection...",
                key="reclassify_reason",
            )
            sub1, sub2, _ = st.columns([1, 1, 3])
            with sub1:
                if st.button("Cancel", key="reclassify_cancel",
                             use_container_width=True):
                    st.session_state["show_reclassify_form"] = False
                    st.rerun()
            with sub2:
                if st.button("Submit", key="reclassify_submit",
                             use_container_width=True, type="primary"):
                    if not reason.strip():
                        st.error("A reason is required to reclassify.")
                    else:
                        reclassify_patient(
                            patient["patient_id"], new_tier,
                            st.session_state["user"]["user_id"], reason,
                        )
                        st.session_state["show_reclassify_form"] = False
                        st.success(f"Patient reclassified to {new_tier}.")
                        st.rerun()


def _render_explanation_panel(patient: dict):
    st.markdown('<div class="section-heading">Why this classification?</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<p class="section-sub">Key clinical drivers contributing to the '
        'current risk score, and how the score has trended over the past 24 hours.</p>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.2, 1], gap="medium")

    with left:
        drivers = get_risk_explanation(patient["patient_id"], top_n=5)

        # Outer panel wrapper
        st.markdown('<div class="driver-panel">', unsafe_allow_html=True)

        if not drivers:
            st.markdown(
                f'<p style="color:{COLORS["ink_soft"]}; font-style:italic; margin:0;">'
                f'No variables are currently outside their reference ranges.</p>',
                unsafe_allow_html=True,
            )
        else:
            # Build a reverse map from pretty name → internal key for LOINC lookup
            pretty_to_key = {
                "Lactate": "lactate", "WBC": "wbc", "Creatinine": "creatinine",
                "Platelets": "platelets", "BUN": "bun", "Glucose": "glucose",
            }

            for i, d in enumerate(drivers):
                arrow = "▲" if d["direction"] == "up" else "▼"
                is_last = (i == len(drivers) - 1)
                border_style = "" if is_last else f"border-bottom: 1px solid {COLORS['cream_dark']};"

                # LOINC reference for labs — vitals don't have LOINC in our set
                lab_key = pretty_to_key.get(d["name"])
                loinc_line = ""
                if lab_key and lab_key in LOINC:
                    loinc_entry = LOINC[lab_key]
                    loinc_line = (
                        f'<div style="font-size:0.7rem; color:{COLORS["ink_light"]}; '
                        f'font-family:monospace; margin-top:0.15rem;">'
                        f'LOINC {loinc_entry["code"]}</div>'
                    )

                st.markdown(
                    f"""
                    <div style="display:flex; align-items:center; justify-content:space-between;
                                padding:0.6rem 0; {border_style}">
                      <div style="width:30%;">
                        <div style="font-weight:600; color:{COLORS['navy_deep']};">
                          {d['name']}
                        </div>
                        {loinc_line}
                      </div>
                      <div style="font-family:'JetBrains Mono',monospace; color:{COLORS['ink']}; width:25%;">
                        {d['value']} {d['unit']}
                      </div>
                      <div style="font-size:0.85rem; width:25%;
                                  color:{COLORS['risk_high'] if d['direction']=='up' else COLORS['info']};">
                        {arrow} {d['status']}
                      </div>
                      <div style="font-family:'JetBrains Mono',monospace; font-weight:600;
                                  color:{COLORS['navy_deep']}; width:20%; text-align:right;">
                        +{d['contribution']:.2f}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        _render_risk_trend_chart(patient)


def _render_risk_trend_chart(patient: dict):
    history = get_risk_history(patient["patient_id"], hours=24)
    tier = patient["risk_tier"]
    tier_color = {
        "High":     COLORS["risk_high"],
        "Moderate": COLORS["risk_moderate"],
        "Low":      COLORS["risk_low"],
    }[tier]

    fig = go.Figure()

    # Main trend line
    fig.add_trace(go.Scatter(
        x=history["hour"],
        y=history["risk_score"],
        mode="lines+markers",
        line=dict(color=tier_color, width=2.5),
        marker=dict(size=5, color=tier_color),
        name="Risk score",
        hovertemplate="Hour %{x}<br>Risk: %{y:.2f}<extra></extra>",
    ))

    # Threshold reference lines — from HW7 tiering conceptually
    fig.add_hline(y=0.30, line_dash="dot", line_color=COLORS["risk_moderate"],
                  opacity=0.5, annotation_text="Moderate",
                  annotation_position="right")
    fig.add_hline(y=0.60, line_dash="dot", line_color=COLORS["risk_high"],
                  opacity=0.5, annotation_text="High",
                  annotation_position="right")

    fig.update_layout(
        title=dict(text="Risk score — last 24 hours", font=dict(size=14,
                   color=COLORS["navy_deep"])),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        xaxis=dict(title="Hours from now", gridcolor=COLORS["cream_dark"],
                   zeroline=False),
        yaxis=dict(title="Risk score", gridcolor=COLORS["cream_dark"],
                   range=[0, 1], zeroline=False),
        margin=dict(l=10, r=10, t=50, b=40),
        height=280,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_recommendations(patient: dict):
    recs = get_recommendations(patient["risk_tier"])

    st.markdown('<div class="section-heading">Preliminary recommendations</div>',
                unsafe_allow_html=True)

    items = "".join(f"<li>{r}</li>" for r in recs)
    st.markdown(
        f"""
        <div class="rec-panel">
          <ul>{items}</ul>
          <div class="rec-disclaimer">
            Recommendations are model-generated and preliminary. Clinical judgment
            supersedes these suggestions. All actions must be documented in the EHR.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# MAIN RENDER — as a modal dialog
# ============================================================
@st.dialog("Patient Risk Assessment Report", width="large")
def render_modal(patient_id: str):
    """Render the full patient risk report inside a Streamlit modal.

    Called from the clinician dashboard when the user clicks '📄 View'.
    The modal's built-in close button returns the user to the dashboard.
    """
    _inject_css()

    if patient_id is None:
        st.warning("No patient selected.")
        return

    patient = get_patient_detail(patient_id)
    if patient is None:
        st.error(f"Patient {patient_id} not found.")
        return

    _render_patient_header(patient)
    _render_risk_banner(patient)
    _render_explanation_panel(patient)
    _render_recommendations(patient)