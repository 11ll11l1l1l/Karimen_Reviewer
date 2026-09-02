"""Regression checks for ALAM's cross-cutting accessibility contract."""

from pathlib import Path

from alam_accessibility import ACCESSIBILITY_CSS


css = ACCESSIBILITY_CSS.replace(" ", "").lower()

# Keyboard focus must remain visible across native Streamlit buttons and semantic
# widget roles even if a later feature module changes ordinary border/shadow styles.
assert ":focus-visible" in css
assert "outline:3pxsolid#1f5eff!important" in css
assert "[role=\"tab\"]:focus-visible" in css
assert "[role=\"radio\"]:focus-visible" in css

# Mobile primary controls use a phone-friendly minimum target rather than relying on
# text height.  The desktop floor remains at least 44px.
assert "min-height:44px" in css
assert "min-height:48px!important" in css

# Motion is presentation-only and must respect the OS accessibility preference.
assert "@media(prefers-reduced-motion:reduce)" in css
assert "animation-duration:.01ms!important" in css
assert "transition-duration:.01ms!important" in css

# Evidence-bearing links must keep a non-colour affordance.
assert "text-decoration:underline" in css

# Install order is part of the contract: accessibility is deliberately last so the
# many independent visual modules cannot silently override it later.
app = Path(__file__).with_name("streamlit_app.py").read_text(encoding="utf-8")
assert "import alam_accessibility as accessibility" in app
assert "accessibility.install_accessibility()" in app
assert app.index("accessibility.install_accessibility()") > app.index("time_theme.install_time_theme()")

print("ALAM accessibility contract regression test passed")
