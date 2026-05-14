"""
SAFE — Top Navigation Bar
-------------------------
Used on every logged-in screen. Shows the SAFE wordmark on the left,
user identity + sign-out on the right.
"""

import streamlit as st
from config.theme import COLORS, RADIUS


def _inject_css():
    st.markdown(
        f"""
        <style>
          .safe-topbar {{
              display: flex;
              align-items: center;
              justify-content: space-between;
              padding: 0.9rem 1.5rem;
              background: #FFFFFF;
              border: 1px solid {COLORS['beige']};
              border-radius: {RADIUS['md']};
              margin-bottom: 1.5rem;
              box-shadow: 0 1px 3px rgba(27, 42, 78, 0.04);
          }}
          .safe-topbar-brand {{
              display: flex;
              align-items: baseline;
              gap: 0.6rem;
          }}
          .safe-topbar-brand .wordmark {{
              font-size: 1.4rem;
              font-weight: 700;
              letter-spacing: 0.04em;
              color: {COLORS['navy_deep']};
          }}
          .safe-topbar-brand .subtitle {{
              font-size: 0.8rem;
              color: {COLORS['ink_soft']};
          }}
          .safe-topbar-user {{
              display: flex;
              align-items: center;
              gap: 1rem;
          }}
          .safe-topbar-user .identity {{
              text-align: right;
              line-height: 1.2;
          }}
          .safe-topbar-user .identity .name {{
              font-size: 0.9rem;
              font-weight: 600;
              color: {COLORS['navy_deep']};
          }}
          .safe-topbar-user .identity .role {{
              font-size: 0.75rem;
              color: {COLORS['ink_soft']};
              text-transform: capitalize;
              letter-spacing: 0.02em;
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render(user: dict, on_signout):
    """Render the top bar.

    Args:
        user: dict with keys 'name' and 'role'
        on_signout: callable invoked when user clicks 'Sign out'
    """
    _inject_css()

    # Render the left/center chrome as HTML; right side as a real button via columns.
    left, right = st.columns([3, 1])

    with left:
        st.markdown(
            f"""
            <div class="safe-topbar" style="margin-bottom:0;">
              <div class="safe-topbar-brand">
                <span class="wordmark">SAFE</span>
                <span class="subtitle">Sepsis Alert &amp; Forecasting Engine</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        c1, c2 = st.columns([2, 1], gap="small")
        with c1:
            st.markdown(
                f"""
                <div style="text-align:right; padding-top:0.6rem;">
                  <div style="font-size:0.9rem; font-weight:600; color:{COLORS['navy_deep']};">
                    {user['name']}
                  </div>
                  <div style="font-size:0.75rem; color:{COLORS['ink_soft']};
                              text-transform:capitalize;">
                    {user['role']}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c2:
            if st.button("Sign out", key="topbar_signout", use_container_width=True):
                on_signout()

    # Small spacer below the bar
    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)