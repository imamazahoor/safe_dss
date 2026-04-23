"""
SAFE — Clinician Patient Queue Dashboard
----------------------------------------
Main workhorse screen for clinical users. Shows a tiered
active-patient queue with per-row actions: view, edit profile,
update clinical measurements (incl. OCR lab upload), discharge.
"""

import streamlit as st
from config.theme import COLORS, RADIUS
from components import top_bar
from services.data_service import (
    get_dashboard_stats,
    get_patients_by_tier,
    get_patient_detail,
    update_patient_profile,
    record_new_measurement,
    discharge_patient,
    admit_patient,
    recompute_risk_for_patient,
)
from screens import patient_detail, high_risk_alert
from services.ocr_service import parse_lab_report


# ============================================================
# CSS — scoped to the dashboard
# ============================================================
def _inject_css():
    st.markdown(
        f"""
        <style>
          /* Welcome line */
          .dash-welcome {{
              margin: 0 0 1.25rem 0;
          }}
          .dash-welcome h2 {{
              margin: 0;
              color: {COLORS['navy_deep']};
              font-size: 1.5rem;
              font-weight: 600;
          }}
          .dash-welcome p {{
              margin: 0.2rem 0 0 0;
              color: {COLORS['ink_soft']};
              font-size: 0.9rem;
          }}

          /* Stat cards */
          .stat-card {{
              background: #FFFFFF;
              border: 1px solid {COLORS['beige']};
              border-radius: {RADIUS['md']};
              padding: 1.1rem 1.3rem;
              box-shadow: 0 1px 3px rgba(27, 42, 78, 0.04);
              height: 100%;
          }}
          .stat-card .label {{
              font-size: 0.8rem;
              color: {COLORS['ink_soft']};
              text-transform: uppercase;
              letter-spacing: 0.05em;
              margin: 0 0 0.4rem 0;
          }}
          .stat-card .value {{
              font-size: 2rem;
              font-weight: 700;
              color: {COLORS['navy_deep']};
              line-height: 1;
              margin: 0;
          }}
          .stat-card .hint {{
              font-size: 0.75rem;
              color: {COLORS['ink_light']};
              margin: 0.4rem 0 0 0;
          }}
          .stat-card.accent-high .value {{ color: {COLORS['risk_high']}; }}
          .stat-card.accent-gold .value {{ color: {COLORS['gold']}; }}

          /* Tier section headers */
          .tier-header {{
              display: flex;
              align-items: center;
              gap: 0.6rem;
              margin: 2rem 0 0.75rem 0;
          }}
          .tier-header .dot {{
              width: 10px; height: 10px; border-radius: 50%;
          }}
          .tier-header h3 {{
              margin: 0;
              font-size: 1.15rem;
              color: {COLORS['navy_deep']};
          }}
          .tier-header .count {{
              font-size: 0.85rem;
              color: {COLORS['ink_soft']};
              background: {COLORS['cream_dark']};
              padding: 0.15rem 0.6rem;
              border-radius: 999px;
          }}

          /* Patient row card */
          .patient-row {{
              background: #FFFFFF;
              border: 1px solid {COLORS['beige']};
              border-radius: {RADIUS['md']};
              padding: 0.9rem 1.1rem;
              margin-bottom: 0.6rem;
              border-left: 4px solid {COLORS['beige']};
          }}
          .patient-row.tier-high     {{ border-left-color: {COLORS['risk_high']}; }}
          .patient-row.tier-moderate {{ border-left-color: {COLORS['risk_moderate']}; }}
          .patient-row.tier-low      {{ border-left-color: {COLORS['risk_low']}; }}

          .patient-row .pid {{
              font-family: 'JetBrains Mono', 'Consolas', monospace;
              font-size: 0.8rem;
              color: {COLORS['ink_soft']};
              letter-spacing: 0.02em;
          }}
          .patient-row .pname {{
              font-size: 1rem;
              font-weight: 600;
              color: {COLORS['navy_deep']};
              margin: 0.1rem 0;
          }}
          .patient-row .pmeta {{
              font-size: 0.82rem;
              color: {COLORS['ink_soft']};
          }}
          .patient-row .score-pill {{
              display: inline-block;
              padding: 0.25rem 0.75rem;
              border-radius: 999px;
              font-size: 0.85rem;
              font-weight: 600;
              font-family: 'JetBrains Mono', 'Consolas', monospace;
          }}
          .score-pill.tier-high     {{ background: {COLORS['risk_high_bg']};   color: {COLORS['risk_high']}; }}
          .score-pill.tier-moderate {{ background: {COLORS['risk_mod_bg']};    color: {COLORS['risk_moderate']}; }}
          .score-pill.tier-low      {{ background: {COLORS['risk_low_bg']};    color: {COLORS['risk_low']}; }}

          /* ── Alert status badges ── */
          .alert-badge {{
              display: inline-block;
              padding: 0.15rem 0.55rem;
              border-radius: 999px;
              font-size: 0.7rem;
              font-weight: 600;
              letter-spacing: 0.04em;
              text-transform: uppercase;
              margin-top: 0.3rem;
          }}
          .alert-badge.overridden {{
              background: #FFFFFF;
              color: {COLORS['ink_soft']};
              border: 1px solid {COLORS['ink_soft']};
          }}
          .alert-badge.acknowledged {{
              background: {COLORS['risk_low_bg']};
              color: {COLORS['risk_low']};
              border: 1px solid {COLORS['risk_low']};
          }}

          /* Empty state */
          .tier-empty {{
              padding: 1rem 1.2rem;
              background: {COLORS['cream_dark']};
              border-radius: {RADIUS['md']};
              color: {COLORS['ink_soft']};
              font-size: 0.9rem;
              font-style: italic;
          }}

          /* OCR status banner (shown inside the Update Clinical modal) */
          .ocr-success {{
              background: {COLORS['risk_low_bg']};
              border-left: 4px solid {COLORS['risk_low']};
              color: {COLORS['risk_low']};
              padding: 0.6rem 0.9rem;
              border-radius: {RADIUS['sm']};
              font-size: 0.85rem;
              margin: 0.5rem 0 1rem 0;
          }}
          /* ── Inline banner (non-high, no tier change) ── */
          .tier-banner {{
              display: flex;
              align-items: center;
              gap: 0.75rem;
              padding: 0.75rem 1.1rem;
              border-radius: {RADIUS['md']};
              margin: 0 0 1.25rem 0;
              font-size: 0.9rem;
          }}
          .tier-banner.tier-low {{
              background: {COLORS['risk_low_bg']};
              border-left: 4px solid {COLORS['risk_low']};
              color: {COLORS['risk_low']};
          }}
          .tier-banner.tier-moderate {{
              background: {COLORS['risk_mod_bg']};
              border-left: 4px solid {COLORS['risk_moderate']};
              color: {COLORS['risk_moderate']};
          }}
          .tier-banner strong {{ color: {COLORS['ink']}; }}
          .tier-banner .icon {{
              font-size: 1.1rem;
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# STAT CARDS
# ============================================================
def _render_stat_cards():
    stats = get_dashboard_stats()
    c1, c2, c3 = st.columns(3, gap="medium")

    with c1:
        st.markdown(
            f"""
            <div class="stat-card">
              <p class="label">Total active patients</p>
              <p class="value">{stats['total_patients']}</p>
              <p class="hint">Currently admitted to ICU</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="stat-card accent-high">
              <p class="label">High-risk alerts</p>
              <p class="value">{stats['high_risk_alerts']}</p>
              <p class="hint">Require immediate attention</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""
            <div class="stat-card accent-gold">
              <p class="label">Avg risk score</p>
              <p class="value">{stats['avg_risk_score']:.2f}</p>
              <p class="hint">Across active cohort</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# PATIENT ROW
# ============================================================
def _render_patient_row(patient: dict, row_key: str):
    """Render one patient row with inline action buttons."""
    tier_class = f"tier-{patient['risk_tier'].lower()}"

    col_info, col_score, col_actions = st.columns([3, 1, 2.5], gap="small")

    with col_info:
        # Build the optional alert status badge
        status = patient.get("alert_status", "none")
        badge_html = ""
        if status == "overridden":
            badge_html = (
                '<span class="alert-badge overridden" '
                'title="Model flagged High; clinician overrode">'
                '⊘ Overridden</span>'
            )
        elif status == "acknowledged":
            badge_html = (
                '<span class="alert-badge acknowledged" '
                'title="High-risk alert acknowledged; interventions in progress">'
                '✓ Acknowledged</span>'
            )

        st.markdown(
            f"""
            <div class="patient-row {tier_class}" style="margin-bottom:0;">
              <div class="pid">{patient['patient_id']}</div>
              <div class="pname">{patient['name']}</div>
              <div class="pmeta">
                {patient['age']}y · {patient['gender']} · {patient['unit']} ·
                ICU hour {patient['icu_hour']}
              </div>
              {badge_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_score:
        # Vertically align the pill with the middle of the patient card
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; justify-content:center;
                        height:100%; min-height:4.2rem;">
              <span class="score-pill {tier_class}">
                {patient['risk_score']:.2f}
              </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_actions:
        a1, a2, a3, a4 = st.columns(4, gap="small")
        pid = patient["patient_id"]

        with a1:
            if st.button("📄 View", key=f"view_{row_key}", use_container_width=True,
                         help="Open full patient summary"):
                st.session_state["modal_target"] = pid
                st.session_state["modal_kind"] = "view"
                st.rerun()
        with a2:
            if st.button("✏️ Edit", key=f"edit_{row_key}", use_container_width=True,
                         help="Edit patient profile"):
                st.session_state["modal_target"] = pid
                st.session_state["modal_kind"] = "edit"
                st.rerun()
        with a3:
            if st.button("🩺 Update", key=f"update_{row_key}", use_container_width=True,
                         help="Update vitals and labs"):
                st.session_state["modal_target"] = pid
                st.session_state["modal_kind"] = "update"
                st.rerun()
        with a4:
            if st.button("↗ Discharge", key=f"discharge_{row_key}", use_container_width=True,
                         help="Discharge from ICU"):
                st.session_state["modal_target"] = pid
                st.session_state["modal_kind"] = "discharge"
                st.rerun()

# ============================================================
# TIERED TABLES
# ============================================================
def _render_tier_section(tier: str, default_expanded: bool = True):
    """Render a collapsible section for one risk tier."""
    patients = get_patients_by_tier(tier)
    dot_color = {
        "High":     COLORS["risk_high"],
        "Moderate": COLORS["risk_moderate"],
        "Low":      COLORS["risk_low"],
    }[tier]

    # Header with dot + title + count badge
    st.markdown(
        f"""
        <div class="tier-header">
          <span class="dot" style="background:{dot_color};"></span>
          <h3>{tier}-risk patients</h3>
          <span class="count">{len(patients)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"{tier}-risk list", expanded=default_expanded):
        # Hide the expander's own label — we have our own header above
        if not patients:
            st.markdown(
                f'<div class="tier-empty">No patients currently in this tier.</div>',
                unsafe_allow_html=True,
            )
            return
        for idx, p in enumerate(patients):
            stable_row_key = f"{tier.lower()}_{idx}_{p['patient_id']}"
            _render_patient_row(p, stable_row_key)

# ============================================================
# RISK NOTIFICATION DISPATCH
# ============================================================
# ============================================================
# RISK NOTIFICATION DISPATCH
# ============================================================
def _dispatch_risk_notification(event: dict):
    """Route a risk-computation event to the right notification channel.

    Three paths:
      1. Tier is High -> interruptive alert modal (acknowledge/override)
      2. Tier changed, not High -> informational tier-change modal
      3. Same tier, not High -> inline banner on dashboard (non-blocking)
    """
    tier = event["risk_tier"]
    tier_changed = event.get("tier_changed", True)  # admits always count as changed

    if tier == "High":
        # Interruptive modal with full acknowledge/override flow
        st.session_state["pending_risk_event"] = event
        st.session_state["modal_target"] = event["patient_id"]
        st.session_state["modal_kind"] = "high_risk_alert"
    elif tier_changed:
        # Informative modal showing the tier transition
        st.session_state["pending_tier_change"] = event
        st.session_state["modal_target"] = event["patient_id"]
        st.session_state["modal_kind"] = "tier_change"
    else:
        # no modal, no interruption
        st.session_state["pending_banner"] = {
            "tier":  tier,
            "name":  event["name"],
            "score": event["risk_score"],
        }


# ============================================================
# MODALS — @st.dialog decorator
# ============================================================
@st.dialog("Edit patient profile", width="large")
def _modal_edit(patient_id: str):
    patient = get_patient_detail(patient_id)
    if patient is None:
        st.error("Patient not found.")
        return

    st.markdown(f"**Patient ID:** `{patient['patient_id']}`")
    new_name = st.text_input("Name", value=patient["name"])
    col1, col2 = st.columns(2)
    with col1:
        new_age = st.number_input("Age", value=int(patient["age"]), min_value=0, max_value=120)
    with col2:
        new_gender = st.selectbox(
            "Gender", ["M", "F", "Other"],
            index=["M", "F", "Other"].index(patient["gender"]) if patient["gender"] in ["M", "F", "Other"] else 0,
        )
    # new_unit = st.selectbox(
    #     "ICU Unit", ["MICU", "SICU", "CCU", "NICU"],
    #     index=["MICU", "SICU", "CCU", "NICU"].index(patient["unit"]) if patient["unit"] in ["MICU", "SICU", "CCU", "NICU"] else 0,
    # )

    st.markdown("---")
    cancel, save = st.columns([1, 1])
    with cancel:
        if st.button("Cancel", key="edit_cancel", use_container_width=True):
            _close_modal()
    with save:
        if st.button("Save changes", key="edit_save", use_container_width=True, type="primary"):
            update_patient_profile(patient_id, {
                "name": new_name, "age": new_age,
                "gender": new_gender,
            })
            _close_modal()


@st.dialog("Update clinical results", width="large")
def _modal_update(patient_id: str):
    patient = get_patient_detail(patient_id)
    if patient is None:
        st.error("Patient not found.")
        return

    st.markdown(f"**Patient:** {patient['name']} · `{patient['patient_id']}`")

    tab_manual, tab_upload = st.tabs(["Manual entry", "Upload lab report"])

    # --- Initialize staged values in session state ---
    # This lets the OCR tab write into the manual tab's field defaults
    stage_key = f"update_stage_{patient_id}"
    if stage_key not in st.session_state:
        st.session_state[stage_key] = {
            "vitals": dict(patient["vitals"]),
            "labs":   dict(patient["labs"]),
        }
    staged = st.session_state[stage_key]

    def _num(value, default: float = 0.0) -> float:
        """Safely coerce optional numeric fields for Streamlit number_input."""
        return default if value is None else float(value)

    # ---------- TAB 1: MANUAL ENTRY ----------
    with tab_manual:
        st.markdown("##### Vitals")
        v1, v2, v3 = st.columns(3)
        with v1:
            hr = st.number_input("Heart rate (bpm)",   value=_num(staged["vitals"].get("hr")),    key=f"v_hr_{patient_id}")
            sbp = st.number_input("SBP (mmHg)",         value=_num(staged["vitals"].get("sbp")),   key=f"v_sbp_{patient_id}")
        with v2:
            map_ = st.number_input("MAP (mmHg)",        value=_num(staged["vitals"].get("map")),   key=f"v_map_{patient_id}")
            temp = st.number_input("Temp (°C)",         value=_num(staged["vitals"].get("temp"), 37.0), key=f"v_temp_{patient_id}", step=0.1, format="%.1f")
        with v3:
            resp = st.number_input("Resp (/min)",       value=_num(staged["vitals"].get("resp")),  key=f"v_resp_{patient_id}")
            o2sat = st.number_input("O2 Sat (%)",       value=_num(staged["vitals"].get("o2sat")), key=f"v_o2_{patient_id}")

        st.markdown("##### Key labs")
        l1, l2, l3 = st.columns(3)
        with l1:
            lactate    = st.number_input("Lactate (mmol/L)",     value=_num(staged["labs"].get("lactate")),   key=f"l_lac_{patient_id}", step=0.1, format="%.1f")
            platelets  = st.number_input("Platelets (x10⁹/L)",   value=_num(staged["labs"].get("platelets")), key=f"l_plt_{patient_id}")
        with l2:
            wbc        = st.number_input("WBC (x10⁹/L)",         value=_num(staged["labs"].get("wbc")),       key=f"l_wbc_{patient_id}", step=0.1, format="%.1f")
            bun        = st.number_input("BUN (mg/dL)",          value=_num(staged["labs"].get("bun")),       key=f"l_bun_{patient_id}")
        with l3:
            creatinine = st.number_input("Creatinine (mg/dL)",   value=_num(staged["labs"].get("creatinine")), key=f"l_cr_{patient_id}",  step=0.1, format="%.1f")
            glucose    = st.number_input("Glucose (mg/dL)",      value=_num(staged["labs"].get("glucose")),    key=f"l_glu_{patient_id}")

        st.markdown("---")
        cancel_c, save_c = st.columns([1, 1])
        with cancel_c:
            if st.button("Cancel", key="update_cancel", use_container_width=True):
                del st.session_state[stage_key]
                _close_modal()
        with save_c:
            if st.button("Save measurement", key="update_save",
                         use_container_width=True, type="primary"):
                record_new_measurement(
                    patient_id,
                    vitals={"hr": hr, "map": map_, "sbp": sbp, "temp": temp,
                            "resp": resp, "o2sat": o2sat},
                    labs={"lactate": lactate, "wbc": wbc, "creatinine": creatinine,
                          "platelets": platelets, "bun": bun, "glucose": glucose},
                )
                del st.session_state[stage_key]

                # Recompute risk against the new snapshot
                event = recompute_risk_for_patient(patient_id)

                # Close this modal, then dispatch a notification
                for k in ("modal_target", "modal_kind"):
                    if k in st.session_state:
                        del st.session_state[k]
                if event is not None:
                    _dispatch_risk_notification(event)
                st.rerun()

    # ---------- TAB 2: UPLOAD LAB REPORT (OCR) ----------
    with tab_upload:
        st.markdown(
            f"""
            <p style="color:{COLORS['ink_soft']}; font-size:0.9rem;">
              Upload a lab report PDF or image. SAFE will automatically parse
              the values and populate the manual entry form, which you can
              review before saving.
            </p>
            """,
            unsafe_allow_html=True,
        )

        uploaded = st.file_uploader(
            "Lab report file",
            type=["pdf", "png", "jpg", "jpeg"],
            key=f"ocr_upload_{patient_id}",
        )

        if uploaded is not None:
            if st.button("Parse lab report", key=f"ocr_parse_{patient_id}",
                         type="primary", use_container_width=True):
                with st.spinner("Parsing lab report…"):
                    parsed = parse_lab_report(uploaded)
                if parsed:
                    # Stage the parsed values for the manual tab
                    staged["labs"].update(parsed)
                    st.session_state[stage_key] = staged
                    st.markdown(
                        f"""
                        <div class="ocr-success">
                          ✓ Parsed {len(parsed)} lab values. Switch to the
                          <strong>Manual entry</strong> tab to review and save.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    # Show what was parsed
                    st.markdown("**Parsed values:**")
                    for k, v in parsed.items():
                        st.markdown(f"- {k.capitalize()}: `{v}`")

        st.caption(
            "Demo note: Any uploaded file "
            "returns a canned set of values. Future versions will use "
            "real OCR + LLM parsing."
        )


@st.dialog("Discharge patient")
def _modal_discharge(patient_id: str):
    patient = get_patient_detail(patient_id)
    if patient is None:
        st.error("Patient not found.")
        return

    st.markdown(
        f"""
        <div style="padding: 0.5rem 0;">
          <p style="font-size:1rem; color:{COLORS['ink']};">
            Are you sure you want to discharge
            <strong>{patient['name']}</strong> (<code>{patient['patient_id']}</code>)?
          </p>
          <p style="color:{COLORS['ink_soft']}; font-size:0.85rem;">
            This will remove the patient from the active queue. The ICU stay record
            will be closed with a discharge timestamp.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cancel, confirm = st.columns([1, 1])
    with cancel:
        if st.button("Cancel", key="discharge_cancel", use_container_width=True):
            _close_modal()
    with confirm:
        if st.button("Discharge", key="discharge_confirm",
                     use_container_width=True, type="primary"):
            if discharge_patient(patient_id):
                _close_modal()
            else:
                st.error("Could not discharge patient. Please try again.")

@st.dialog("Admit new patient", width="large")
def _modal_admit(_unused: str):
    """Two-tab intake flow: Profile + Vitals, then Labs. Final step shows
    the computed risk tier briefly before closing.
    """


    # ---------- STAGED STATE: collect values across tabs ----------
    stage_key = "admit_stage"
    if stage_key not in st.session_state:
        st.session_state[stage_key] = {
            "vitals": {"hr": 80.0, "map": 75.0, "sbp": 120.0,
                       "temp": 37.0, "resp": 18.0, "o2sat": 97.0},
            "labs":   {"lactate": None, "wbc": None, "creatinine": None,
                       "platelets": None, "bun": None, "glucose": None},
        }
    staged = st.session_state[stage_key]

    tab_profile, tab_labs = st.tabs(["Profile + Vitals", "Initial Labs"])

    # ---------- TAB 1: Profile + Vitals (required) ----------
    with tab_profile:
        st.markdown("##### Patient profile")
        name = st.text_input("Name *", key="admit_name",
                             placeholder="e.g., John Smith")
        p1, p2, p3 = st.columns(3)
        with p1:
            age = st.number_input("Age *", min_value=0, max_value=120,
                                  value=55, key="admit_age")
        with p2:
            gender = st.selectbox("Gender *", ["M", "F", "Other"],
                                  key="admit_gender")
        with p3:
            unit = st.selectbox("ICU Unit *",
                                ["MICU", "SICU", "CCU", "NICU"],
                                key="admit_unit")

        st.markdown("##### Admission vitals")
        v1, v2, v3 = st.columns(3)
        with v1:
            hr = st.number_input("Heart rate (bpm)",
                                 value=float(staged["vitals"]["hr"]),
                                 key="admit_hr")
            sbp = st.number_input("SBP (mmHg)",
                                  value=float(staged["vitals"]["sbp"]),
                                  key="admit_sbp")
        with v2:
            map_ = st.number_input("MAP (mmHg)",
                                   value=float(staged["vitals"]["map"]),
                                   key="admit_map")
            temp = st.number_input("Temp (°C)",
                                   value=float(staged["vitals"]["temp"]),
                                   key="admit_temp",
                                   step=0.1, format="%.1f")
        with v3:
            resp = st.number_input("Resp (/min)",
                                   value=float(staged["vitals"]["resp"]),
                                   key="admit_resp")
            o2sat = st.number_input("O2 Sat (%)",
                                    value=float(staged["vitals"]["o2sat"]),
                                    key="admit_o2")

    # ---------- TAB 2: Initial Labs (manual or OCR) ----------
    with tab_labs:
        st.markdown(
            f"""
            <p style="color:{COLORS['ink_soft']}; font-size:0.9rem;">
              Enter at least one lab value to admit the patient. You can upload
              a lab report PDF/image to auto-parse values, or enter them manually.
              Labs not available at admission can be added later via the
              <strong>Update Clinical Results</strong> action.
            </p>
            """,
            unsafe_allow_html=True,
        )

        # OCR upload (reuses existing service)
        uploaded = st.file_uploader(
            "Upload initial lab report (optional)",
            type=["pdf", "png", "jpg", "jpeg"],
            key="admit_ocr_upload",
        )
        if uploaded is not None:
            if st.button("Parse lab report", key="admit_ocr_parse",
                         use_container_width=True):
                with st.spinner("Parsing lab report…"):
                    parsed = parse_lab_report(uploaded)
                if parsed:
                    staged["labs"].update(parsed)
                    st.session_state[stage_key] = staged
                    st.success(f"Parsed {len(parsed)} lab values. Review below.")
                    st.rerun()

        st.markdown("##### Key labs")
        l1, l2, l3 = st.columns(3)
        # Labs can be blank → use None to mean "not drawn"
        # We use text_input with validation instead of number_input so empty
        # strings are allowed (number_input requires a value)
        def _num_or_none(raw: str):
            raw = raw.strip()
            if not raw:
                return None
            try:
                return float(raw)
            except ValueError:
                return None

        def _staged_str(labname: str) -> str:
            v = staged["labs"].get(labname)
            return "" if v is None else str(v)

        with l1:
            lactate_s    = st.text_input("Lactate (mmol/L)",
                                         value=_staged_str("lactate"),
                                         key="admit_lac")
            platelets_s  = st.text_input("Platelets (x10⁹/L)",
                                         value=_staged_str("platelets"),
                                         key="admit_plt")
        with l2:
            wbc_s        = st.text_input("WBC (x10⁹/L)",
                                         value=_staged_str("wbc"),
                                         key="admit_wbc")
            bun_s        = st.text_input("BUN (mg/dL)",
                                         value=_staged_str("bun"),
                                         key="admit_bun")
        with l3:
            creatinine_s = st.text_input("Creatinine (mg/dL)",
                                         value=_staged_str("creatinine"),
                                         key="admit_cr")
            glucose_s    = st.text_input("Glucose (mg/dL)",
                                         value=_staged_str("glucose"),
                                         key="admit_glu")

    # ---------- SUBMIT / CANCEL (render below the tabs) ----------
    st.markdown("---")
    cancel_c, submit_c = st.columns([1, 1])
    with cancel_c:
        if st.button("Cancel", key="admit_cancel", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("admit_") or k in ("modal_target", "modal_kind"):
                    del st.session_state[k]
            st.rerun()
    with submit_c:
        if st.button("Admit patient", key="admit_submit",
                     use_container_width=True, type="primary"):
            # --- validation ---
            errors = []
            if not (name or "").strip():
                errors.append("Patient name is required.")

            labs_submitted = {
                "lactate":    _num_or_none(lactate_s),
                "wbc":        _num_or_none(wbc_s),
                "creatinine": _num_or_none(creatinine_s),
                "platelets":  _num_or_none(platelets_s),
                "bun":        _num_or_none(bun_s),
                "glucose":    _num_or_none(glucose_s),
            }
            if all(v is None for v in labs_submitted.values()):
                errors.append("At least one lab value is required.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                result = admit_patient(
                    name=name.strip(),
                    age=age,
                    gender=gender,
                    unit=unit,
                    vitals={"hr": hr, "map": map_, "sbp": sbp,
                            "temp": temp, "resp": resp, "o2sat": o2sat},
                    labs={k: v for k, v in labs_submitted.items() if v is not None},
                )
                # Close this modal cleanly, then dispatch to the unified
                # notification system (high-risk modal, tier-change modal,
                # or inline banner — whichever fits).
                for k in list(st.session_state.keys()):
                    if k.startswith("admit_") or k in ("modal_target", "modal_kind"):
                        del st.session_state[k]
                _dispatch_risk_notification(result)
                st.rerun()

@st.dialog("Risk assessment updated")
def _modal_tier_change(_unused: str):
    """Informational modal shown when risk tier changes to Low or Moderate.
    Not used for High tier (that path uses the interruptive alert modal).
    """
    event = st.session_state.get("pending_tier_change")
    if event is None:
        return

    tier = event["risk_tier"]
    previous = event.get("previous_tier")
    score = event["risk_score"]
    triggered = event.get("triggered_criteria", [])

    tier_colors = {
        "Low":      (COLORS["risk_low"],      COLORS["risk_low_bg"]),
        "Moderate": (COLORS["risk_moderate"], COLORS["risk_mod_bg"]),
    }
    fg, bg = tier_colors.get(tier, (COLORS["ink"], COLORS["cream_dark"]))

    # Direction framing — is this a better or worse state?
    direction_text = ""
    if previous is None:
        direction_text = "Initial assessment on admission"
    elif previous == tier:
        direction_text = "No change"
    else:
        severity = {"Low": 0, "Moderate": 1, "High": 2}
        if severity.get(tier, 0) > severity.get(previous, 0):
            direction_text = "⚠ Risk increased"
        else:
            direction_text = "✓ Risk decreased"

    # Transition display — "MODERATE (from Low)" style
    if previous and previous != tier:
        transition = f"{tier.upper()} <span style='color:{COLORS['ink_soft']};' \
            font-weight:400;'>(from {previous})</span>"
    else:
        transition = tier.upper()

    st.markdown(
        f"""
        <div style="background:{bg}; border-left:6px solid {fg};
                    padding:1.5rem 1.75rem; border-radius:8px;
                    margin: 0.5rem 0 1rem 0;">
          <div style="font-size:0.8rem; color:{COLORS['ink_soft']};
                      text-transform:uppercase; letter-spacing:0.08em;
                      margin-bottom:0.4rem;">
            {direction_text}
          </div>
          <div style="font-size:1.5rem; font-weight:700; color:{fg};
                      margin-bottom:0.3rem;">
            Risk tier: {transition}
          </div>
          <div style="color:{COLORS['ink']}; font-size:0.95rem;
                      margin-bottom:0.75rem;">
            <strong>{event['name']}</strong> · <code>{event['patient_id']}</code> ·
            score <strong>{score:.2f}</strong>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Triggered criteria section
    if triggered:
        criteria_html = "".join(
            f'<li style="margin-bottom:0.3rem;">{c}</li>' for c in triggered
        )
        st.markdown(
            f"""
            <div style="margin-bottom:1rem;">
              <div style="font-size:0.9rem; font-weight:600;
                          color:{COLORS['navy_deep']}; margin-bottom:0.5rem;">
                Contributing criteria ({len(triggered)})
              </div>
              <ul style="margin:0; padding-left:1.25rem; color:{COLORS['ink']};
                         font-size:0.9rem;">
                {criteria_html}
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<p style="color:{COLORS["ink_soft"]}; font-style:italic; '
            f'font-size:0.9rem; margin-bottom:1rem;">No SAFE criteria currently '
            f'triggered at this assessment.</p>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    if st.button("Got it", key="tier_change_ack",
                 use_container_width=True, type="primary"):
        for k in ("pending_tier_change", "modal_target", "modal_kind"):
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()


def _close_modal():
    """Clear modal session state and rerun to dismiss the dialog."""
    for k in ("modal_target", "modal_kind"):
        if k in st.session_state:
            del st.session_state[k]
    st.rerun()


# ============================================================
# MAIN RENDER
# ============================================================
def render(on_signout):
    """Render the full clinician dashboard.

    Args:
        on_signout: callable passed from app.py router
    """
    _inject_css()

    user = st.session_state["user"]

    # --- Top bar ---
    top_bar.render(user, on_signout)

    # --- Inline risk-update banner (non-high, no tier change) ---
    # Lives at the top of the dashboard and clears on the next full user
    # interaction (any rerun that doesn't re-stash the banner removes it).
    banner = st.session_state.pop("pending_banner", None)
    if banner is not None:
        tier = banner["tier"]
        tier_class = f"tier-{tier.lower()}"
        icon = "●"  # neutral dot; we use tier color for the semantics
        st.markdown(
            f"""
            <div class="tier-banner {tier_class}">
              <span class="icon">{icon}</span>
              <span>
                <strong>{banner['name']}</strong> — risk remains
                {tier.lower()} (score {banner['score']:.2f}). Vitals saved.
              </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --- Welcome line + "+ New Patient" action ---
    welcome_col, action_col = st.columns([4, 1], gap="small")
    with welcome_col:
        st.markdown(
            f"""
            <div class="dash-welcome">
              <h2>Welcome, {user['name']}</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with action_col:
        # Small vertical padding to align the button with the welcome text
        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
        if st.button("＋ New Patient", key="open_admit_modal",
                     use_container_width=True, type="primary"):
            st.session_state["modal_target"] = "new"
            st.session_state["modal_kind"] = "admit"
            st.rerun()

    # --- Stat cards ---
    _render_stat_cards()

    # --- Tiered patient tables ---
    _render_tier_section("High",     default_expanded=True)
    _render_tier_section("Moderate", default_expanded=True)
    _render_tier_section("Low",      default_expanded=False)

    # --- Modal dispatch ---
    kind = st.session_state.get("modal_kind")
    target = st.session_state.get("modal_target")
    if kind and target:
        if kind == "view":
            patient_detail.render_modal(target)
        elif kind == "edit":
            _modal_edit(target)
        elif kind == "update":
            _modal_update(target)
        elif kind == "discharge":
            _modal_discharge(target)
        elif kind == "admit":
            _modal_admit(target)
        elif kind == "high_risk_alert":
            event = st.session_state.get("pending_risk_event")
            if event is not None:
                high_risk_alert.render_modal(event)
        elif kind == "tier_change":
            _modal_tier_change(target)