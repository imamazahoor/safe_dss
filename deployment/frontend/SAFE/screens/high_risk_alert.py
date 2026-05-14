"""
SAFE — High-Risk Alert Modal
----------------------------
Interruptive alert for patients newly classified as High risk.
Shows patient context, top risk drivers, and two action paths:
  - Acknowledge and Act  → Hour-1 sepsis bundle checklist
  - Dismiss / Override   → structured reason (category + required text)
"""

import streamlit as st
from config.theme import COLORS, RADIUS
from services.data_service import (
    get_risk_explanation,
    log_high_risk_acknowledgment,
    log_high_risk_override,
    OVERRIDE_REASON_CATEGORIES,
)


# Hour-1 sepsis bundle, per Surviving Sepsis Campaign guidelines
HOUR_1_BUNDLE = [
    "Measure lactate level (redraw if ≥ 2 mmol/L).",
    "Obtain blood cultures prior to administering antibiotics.",
    "Administer broad-spectrum antibiotics.",
    "Begin rapid administration of 30 mL/kg crystalloid for hypotension or lactate ≥ 4 mmol/L.",
    "Apply vasopressors if MAP remains < 65 mmHg after fluid resuscitation.",
    "Escalate to attending physician / activate rapid response team.",
]


def _inject_css():
    st.markdown(
        f"""
        <style>
          .hra-banner {{
              background: {COLORS['risk_high_bg']};
              border-left: 6px solid {COLORS['risk_high']};
              border-radius: {RADIUS['md']};
              padding: 1.25rem 1.5rem;
              margin: 0.5rem 0 1.25rem 0;
          }}
          .hra-banner .eyebrow {{
              font-size: 0.8rem;
              text-transform: uppercase;
              letter-spacing: 0.08em;
              color: {COLORS['risk_high']};
              font-weight: 600;
              margin-bottom: 0.3rem;
          }}
          .hra-banner .title {{
              font-size: 1.4rem;
              font-weight: 700;
              color: {COLORS['risk_high']};
              margin: 0 0 0.3rem 0;
              line-height: 1.2;
          }}
          .hra-banner .patient-line {{
              color: {COLORS['ink']};
              font-size: 0.95rem;
          }}
          .hra-banner .score {{
              display: inline-block;
              margin-left: 0.5rem;
              font-family: 'JetBrains Mono', 'Consolas', monospace;
              font-weight: 700;
              color: {COLORS['risk_high']};
          }}

          .hra-drivers-heading {{
              font-size: 0.95rem;
              font-weight: 600;
              color: {COLORS['navy_deep']};
              margin: 0.75rem 0 0.5rem 0;
          }}
          .hra-driver-chip {{
              display: inline-block;
              background: #FFFFFF;
              border: 1px solid {COLORS['beige']};
              border-radius: 999px;
              padding: 0.3rem 0.75rem;
              margin: 0 0.4rem 0.4rem 0;
              font-size: 0.85rem;
              color: {COLORS['ink']};
          }}
          .hra-driver-chip .arrow-up   {{ color: {COLORS['risk_high']}; font-weight: 600; }}
          .hra-driver-chip .arrow-down {{ color: {COLORS['info']};      font-weight: 600; }}

          .hra-bundle-heading {{
              font-size: 1rem;
              font-weight: 600;
              color: {COLORS['navy_deep']};
              margin: 1rem 0 0.5rem 0;
          }}
          .hra-override-heading {{
              font-size: 1rem;
              font-weight: 600;
              color: {COLORS['navy_deep']};
              margin: 1rem 0 0.5rem 0;
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.dialog("High-risk sepsis alert", width="large")
def render_modal(event: dict):
    """Render the interruptive high-risk alert dialog.

    Args:
        event: dict returned by admit_patient / recompute_risk_for_patient.
               Must include patient_id, name, unit, risk_score, risk_tier.
    """
    _inject_css()
    user = st.session_state.get("user", {})

    # --- Top banner ---
    st.markdown(
        f"""
        <div class="hra-banner">
          <div class="eyebrow">Immediate action required</div>
          <div class="title">HIGH risk of sepsis detected</div>
          <div class="patient-line">
            <strong>{event['name']}</strong>
            · <code>{event['patient_id']}</code>
            · {event['unit']}
            <span class="score">Score {event['risk_score']:.2f}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Top drivers as chips ---
    drivers = get_risk_explanation(event["patient_id"], top_n=4)
    if drivers:
        st.markdown('<div class="hra-drivers-heading">Top contributing drivers</div>',
                    unsafe_allow_html=True)
        chips = ""
        for d in drivers:
            arrow_cls = "arrow-up" if d["direction"] == "up" else "arrow-down"
            arrow_sym = "▲" if d["direction"] == "up" else "▼"
            chips += (
                f'<span class="hra-driver-chip">'
                f'<strong>{d["name"]}</strong> {d["value"]} {d["unit"]} '
                f'<span class="{arrow_cls}">{arrow_sym}</span>'
                f'</span>'
            )
        st.markdown(chips, unsafe_allow_html=True)

    # --- Path selector ---
    # Track which path the clinician is on (default = none chosen yet)
    path_key = f"hra_path_{event['patient_id']}"
    if path_key not in st.session_state:
        st.session_state[path_key] = None
    chosen_path = st.session_state[path_key]

    # Before choice: show the two primary action buttons
    if chosen_path is None:
        st.markdown("---")
        c1, c2 = st.columns([1, 1], gap="medium")
        with c1:
            if st.button("✓ Acknowledge and act",
                         key=f"hra_ack_{event['patient_id']}",
                         use_container_width=True, type="primary"):
                st.session_state[path_key] = "ack"
                st.rerun()
        with c2:
            if st.button("✕ Dismiss / override",
                         key=f"hra_override_{event['patient_id']}",
                         use_container_width=True):
                st.session_state[path_key] = "override"
                st.rerun()
        return

    # --- Path: Acknowledge and Act ---
    if chosen_path == "ack":
        _render_acknowledge_path(event, user)
        return

    # --- Path: Dismiss / Override ---
    if chosen_path == "override":
        _render_override_path(event, user)
        return


def _render_acknowledge_path(event: dict, user: dict):
    st.markdown('<div class="hra-bundle-heading">Hour-1 sepsis bundle</div>',
                unsafe_allow_html=True)
    st.markdown(
        f'<p style="color:{COLORS["ink_soft"]}; font-size:0.85rem; '
        f'margin-top:0;">Check off each action as initiated. All items '
        f'timestamp-logged to the audit trail.</p>',
        unsafe_allow_html=True,
    )

    selected = []
    for i, item in enumerate(HOUR_1_BUNDLE):
        key = f"hra_bundle_{event['patient_id']}_{i}"
        if st.checkbox(item, key=key):
            selected.append(item)

    notes = st.text_area(
        "Clinical notes (optional)",
        key=f"hra_ack_notes_{event['patient_id']}",
        placeholder="e.g., Cultures drawn, ceftriaxone initiated at 14:32...",
        height=80,
    )

    st.markdown("---")
    back_c, submit_c = st.columns([1, 1])
    with back_c:
        if st.button("← Back", key=f"hra_ack_back_{event['patient_id']}",
                     use_container_width=True):
            st.session_state[f"hra_path_{event['patient_id']}"] = None
            st.rerun()
    with submit_c:
        # Require at least one intervention to be selected
        if st.button("Log response", key=f"hra_ack_submit_{event['patient_id']}",
                     use_container_width=True, type="primary"):
            if not selected:
                st.error("Select at least one intervention before logging.")
            else:
                log_high_risk_acknowledgment(
                    patient_id=event["patient_id"],
                    user_id=user.get("user_id", 0),
                    selected_interventions=selected,
                    notes=notes,
                )
                st.success(f"Response logged. {len(selected)} interventions initiated.")
                _cleanup_and_close(event["patient_id"])


def _render_override_path(event: dict, user: dict):
    st.markdown('<div class="hra-override-heading">Override this alert</div>',
                unsafe_allow_html=True)
    st.markdown(
        f'<p style="color:{COLORS["ink_soft"]}; font-size:0.85rem; '
        f'margin-top:0;">Select a category and provide a clinical '
        f'justification. This feedback improves future alert accuracy.</p>',
        unsafe_allow_html=True,
    )

    category = st.selectbox(
        "Reason category *",
        options=OVERRIDE_REASON_CATEGORIES,
        key=f"hra_override_cat_{event['patient_id']}",
    )
    reason_text = st.text_area(
        "Clinical justification *",
        key=f"hra_override_reason_{event['patient_id']}",
        placeholder="e.g., Patient's elevated lactate is from post-op tissue hypoperfusion, "
                    "not sepsis. Cultures negative ×48h. Source control confirmed.",
        height=100,
    )

    st.markdown("---")
    back_c, submit_c = st.columns([1, 1])
    with back_c:
        if st.button("← Back", key=f"hra_override_back_{event['patient_id']}",
                     use_container_width=True):
            st.session_state[f"hra_path_{event['patient_id']}"] = None
            st.rerun()
    with submit_c:
        if st.button("Submit override",
                     key=f"hra_override_submit_{event['patient_id']}",
                     use_container_width=True, type="primary"):
            if not reason_text.strip():
                st.error("A clinical justification is required to override.")
            else:
                log_high_risk_override(
                    patient_id=event["patient_id"],
                    user_id=user.get("user_id", 0),
                    reason_category=category,
                    reason_text=reason_text.strip(),
                )
                st.success("Override logged to audit trail.")
                _cleanup_and_close(event["patient_id"])


def _cleanup_and_close(patient_id: str):
    """Clear high-risk alert session state and close the modal."""
    keys_to_clear = [
        f"hra_path_{patient_id}",
        f"hra_ack_notes_{patient_id}",
        f"hra_override_cat_{patient_id}",
        f"hra_override_reason_{patient_id}",
        "pending_risk_event",
        "modal_target",
        "modal_kind",
    ]
    # Also clear bundle checkboxes
    for i in range(len(HOUR_1_BUNDLE)):
        keys_to_clear.append(f"hra_bundle_{patient_id}_{i}")

    for k in keys_to_clear:
        if k in st.session_state:
            del st.session_state[k]

    st.rerun()