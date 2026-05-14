"""
SAFE — Sepsis Alert & Forecasting Engine
Entry point + router.
Run with: streamlit run app.py
"""

import streamlit as st
from config.theme import apply_theme, COLORS
from screens import login, clinician_dashboard, admin_dashboard

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="SAFE - Sepsis Alert & Forecasting Engine",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_theme()


# ============================================================
# SESSION STATE
# ============================================================
def _init_session():
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("route", "dashboard")


_init_session()


def logout():
    """Clear auth and modal state, return to login."""
    keys_to_clear = ["authenticated", "user", "route",
                     "modal_target", "modal_kind",
                     "selected_patient_id"]
    for k in keys_to_clear:
        if k in st.session_state:
            del st.session_state[k]
    st.rerun()

# ============================================================
# ROUTER
# ============================================================
if not st.session_state["authenticated"]:
    login.render()
else:
    role = st.session_state["user"]["role"]
    route = st.session_state.get("route", "dashboard")

    if role == "admin":
        admin_dashboard.render(on_signout=logout)
    elif role == "clinician":
        clinician_dashboard.render(on_signout=logout)
    else:
        st.error(f"Unknown role: {role}")
        if st.button("Sign out"):
            logout()