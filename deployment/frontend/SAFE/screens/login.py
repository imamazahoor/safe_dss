"""
SAFE — Login Screen
-------------------
Role-gated authentication. User picks Admin or Clinician,
enters credentials, and is routed to the appropriate dashboard.
"""

import streamlit as st
from config.theme import COLORS, RADIUS
from services.data_service import authenticate_user, log_login_attempt


def _render_card_css():
    """Scoped CSS for the login screen."""
    st.markdown(
        f"""
        <style>
          /* ── Brand header ── */
          .login-brand {{
              text-align: center;
              margin: 0 0 2rem 0;
          }}
          .login-brand h1 {{
              font-size: 2.6rem;
              margin: 0;
              letter-spacing: 0.04em;
              color: {COLORS['navy_deep']};
              font-weight: 700;
          }}
          .login-brand p {{
              color: {COLORS['ink_soft']};
              margin: 0.4rem 0 0 0;
              font-size: 0.95rem;
          }}

          .role-label {{
              color: {COLORS['ink_soft']};
              font-size: 0.9rem;
              font-weight: 500;
              text-align: center;
              margin: 0 0 1rem 0;
          }}

          /* ── Card styling — scoped to our marker so it only hits the login card ── */
          /* The marker is an empty div we inject right before the columns. */
          .login-card-marker + div[data-testid="stHorizontalBlock"]
              > div[data-testid="column"]:nth-child(2) {{
              background: #FFFFFF;
              border: 1px solid {COLORS['beige']};
              border-radius: {RADIUS['lg']};
              padding: 2.5rem 2.5rem 2rem 2.5rem !important;
              box-shadow: 0 4px 24px rgba(27, 42, 78, 0.06);
              margin-top: 4rem;
          }}

          /* ── Tab buttons (kind-based styling) ── */
          .stButton > button[kind="secondary"] {{
              background-color: {COLORS['cream_dark']} !important;
              color: {COLORS['ink_soft']} !important;
              border: 1px solid {COLORS['beige']} !important;
              box-shadow: none !important;
              font-weight: 500 !important;
          }}
          .stButton > button[kind="secondary"]:hover {{
              background-color: {COLORS['beige']} !important;
              color: {COLORS['navy_deep']} !important;
              border-color: {COLORS['navy_soft']} !important;
          }}
          .stButton > button[kind="primary"] {{
              background-color: {COLORS['navy_deep']} !important;
              color: {COLORS['cream']} !important;
              border: 1px solid {COLORS['navy_deep']} !important;
              font-weight: 500 !important;
          }}
          .stButton > button[kind="primary"]:hover {{
              background-color: {COLORS['navy']} !important;
              border-color: {COLORS['navy']} !important;
              color: {COLORS['cream']} !important;
          }}

          /* Error banner */
          .login-error {{
              background: {COLORS['risk_high_bg']};
              border-left: 4px solid {COLORS['risk_high']};
              color: {COLORS['risk_high']};
              padding: 0.75rem 1rem;
              border-radius: {RADIUS['sm']};
              font-size: 0.9rem;
              margin-top: 1rem;
          }}

          /* Small breathing room below the tab row */
          .tab-spacer {{ height: 1.25rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_role_tabs():
    """Two buttons styled as tabs via Streamlit's primary/secondary kind."""
    if "login_selected_role" not in st.session_state:
        st.session_state["login_selected_role"] = "admin"

    current = st.session_state["login_selected_role"]
    col_a, col_b = st.columns(2, gap="small")

    with col_a:
        if st.button(
            "Admin",
            key="tab_admin",
            use_container_width=True,
            type="primary" if current == "admin" else "secondary",
        ):
            if current != "admin":
                st.session_state["login_selected_role"] = "admin"
                st.rerun()

    with col_b:
        if st.button(
            "Clinician",
            key="tab_clinician",
            use_container_width=True,
            type="primary" if current == "clinician" else "secondary",
        ):
            if current != "clinician":
                st.session_state["login_selected_role"] = "clinician"
                st.rerun()

    st.markdown('<div class="tab-spacer"></div>', unsafe_allow_html=True)
    return st.session_state["login_selected_role"]


def render():
    """Render the login screen. Sets st.session_state on successful auth."""
    _render_card_css()

    # Marker div — the CSS uses `+` sibling selector to find the column block
    # that immediately follows this marker, so only THIS set of columns gets
    # card styling. Nested columns elsewhere are untouched.
    st.markdown('<div class="login-card-marker"></div>', unsafe_allow_html=True)

    _, center, _ = st.columns([1, 1.2, 1])

    with center:
        # Brand header
        st.markdown(
            """
            <div class="login-brand">
              <h1>SAFE</h1>
              <p>Sepsis Alert &amp; Forecasting Engine</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Role selector
        st.markdown(
            '<div class="role-label">Please select your role</div>',
            unsafe_allow_html=True,
        )
        selected_role = _render_role_tabs()

        # Credentials
        username = st.text_input(
            "Username",
            placeholder="Enter your username",
            key="login_username",
        )
        password = st.text_input(
            "Password",
            placeholder="Enter your password",
            type="password",
            key="login_password",
        )

        # Submit
        sign_in_clicked = st.button(
            "Sign In",
            use_container_width=True,
            type="primary",
            key="login_submit",
        )

        if sign_in_clicked:
            if not username or not password:
                st.markdown(
                    '<div class="login-error">Please enter both username and password.</div>',
                    unsafe_allow_html=True,
                )
                return

            user = authenticate_user(username, password, selected_role)
            log_login_attempt(username, success=user is not None, role=selected_role)

            if user is None:
                st.markdown(
                    '<div class="login-error">Invalid credentials for the selected role.</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.session_state["authenticated"] = True
                st.session_state["user"] = user
                st.rerun()