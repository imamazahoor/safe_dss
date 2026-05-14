"""
SAFE Design System
------------------
Central source of truth for colors, typography, and spacing.
Every screen imports from this file to stay visually cohesive.
"""

# ============================================================
# COLOR PALETTE — Warm Professional
# ============================================================
# Primary: soft navy (trustworthy, clinical, but warmer than cold blue)
# Neutrals: cream/beige (softer than stark white, easier on eyes)
# Accents: muted gold for highlights, soft terracotta for warmth
# Risk tiers: preserved clinical green/amber/red — these are non-negotiable

COLORS = {
    # Primary brand
    "navy_deep":     "#1B2A4E",   # headers, primary buttons, logo
    "navy":          "#2C4172",   # secondary surfaces, nav bar
    "navy_soft":     "#4A6094",   # hover states, links

    # Warm neutrals (backgrounds)
    "cream":         "#F9F5EE",   # main page background
    "cream_dark":    "#EFE8DA",   # card backgrounds, subtle zones
    "beige":         "#D9CFB8",   # borders, dividers

    # Text
    "ink":           "#1A1A2E",   # primary text
    "ink_soft":      "#5A5A6E",   # secondary text, captions
    "ink_light":     "#8A8A9A",   # disabled, placeholder

    # Accents
    "gold":          "#C9A961",   # highlights, badges
    "terracotta":    "#B5654A",   # secondary CTAs, subtle warmth

    # Risk tiers (clinical — DO NOT change hues, only shades)
    "risk_low":      "#4A7C59",   # green — stable
    "risk_low_bg":   "#E3EDE5",
    "risk_moderate": "#C9923E",   # amber — watch
    "risk_mod_bg":   "#F6ECD8",
    "risk_high":     "#B03A3A",   # red — escalate
    "risk_high_bg":  "#F4DDDD",

    # Functional
    "success":       "#4A7C59",
    "warning":       "#C9923E",
    "danger":        "#B03A3A",
    "info":          "#4A6094",
}

# ============================================================
# TYPOGRAPHY
# ============================================================
FONTS = {
    "heading": "'Inter', 'Segoe UI', sans-serif",
    "body":    "'Inter', 'Segoe UI', sans-serif",
    "mono":    "'JetBrains Mono', 'Consolas', monospace",  # for patient IDs, timestamps
}

# ============================================================
# SPACING & SIZING (in rem for accessibility)
# ============================================================
SPACING = {
    "xs": "0.25rem",
    "sm": "0.5rem",
    "md": "1rem",
    "lg": "1.5rem",
    "xl": "2rem",
    "xxl": "3rem",
}

RADIUS = {
    "sm": "4px",
    "md": "8px",
    "lg": "12px",
    "pill": "999px",
}


# ============================================================
# GLOBAL CSS — injected once per page via apply_theme()
# ============================================================
def get_global_css() -> str:
    """Returns the CSS string to inject into every Streamlit page."""
    return f"""
    <style>
      /* Import web font */
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

      /* App background */
      .stApp {{
          background-color: {COLORS['cream']};
          color: {COLORS['ink']};
          font-family: {FONTS['body']};
      }}

      /* Headings */
      h1, h2, h3, h4, h5, h6 {{
          font-family: {FONTS['heading']};
          color: {COLORS['navy_deep']};
          font-weight: 600;
          letter-spacing: -0.01em;
      }}

      h1 {{ font-size: 2rem; }}
      h2 {{ font-size: 1.5rem; }}
      h3 {{ font-size: 1.2rem; }}

      /* Sidebar */
      section[data-testid="stSidebar"] {{
          background-color: {COLORS['cream_dark']};
          border-right: 1px solid {COLORS['beige']};
      }}

      /* Input fields */
      .stTextInput > div > div > input,
      .stSelectbox > div > div {{
          border-radius: {RADIUS['md']};
          border: 1px solid {COLORS['beige']};
          background-color: #FFFFFF;
      }}

      /* Hide Streamlit's default chrome for a cleaner demo */
      #MainMenu {{ visibility: hidden; }}
      footer {{ visibility: hidden; }}
      header[data-testid="stHeader"] {{
          display: none !important;
      }}
      /* Reclaim the top padding that the hidden header left behind */
      .stApp > header {{ display: none !important; }}
      .block-container {{
          padding-top: 1rem !important;
      }}
    </style>
    """


def apply_theme():
    """Call this at the top of every screen to apply the SAFE theme."""
    import streamlit as st
    st.markdown(get_global_css(), unsafe_allow_html=True)