"""Cross-cutting accessibility safeguards for the ALAM Streamlit UI.

ALAM deliberately has several visual modules because story cards, evidence, saved
state, panels, and the Japan-time atmosphere evolved independently.  That makes
accessibility rules vulnerable to install-order regressions: a later style sheet can
silently shrink a touch target or suppress a browser focus ring.

This module is therefore intentionally small and installed *last*.  It owns only
cross-cutting interaction safeguards, not visual branding.  Keeping these rules in a
single late layer makes the product contract testable without forcing every feature
module to duplicate the same CSS.
"""

from __future__ import annotations

import streamlit as st


ACCESSIBILITY_CSS = r"""
<style>
/* Keyboard users must always be able to see where interaction will occur.  The
   outline is restricted to :focus-visible so ordinary pointer taps do not receive
   a persistent focus decoration. */
button:focus-visible,
a:focus-visible,
input:focus-visible,
textarea:focus-visible,
select:focus-visible,
[role="button"]:focus-visible,
[role="tab"]:focus-visible,
[role="radio"]:focus-visible {
  outline:3px solid #1F5EFF !important;
  outline-offset:3px !important;
  box-shadow:0 0 0 2px rgba(255,255,255,.96) !important;
}

/* Streamlit can render navigation choices as buttons, radio-like controls, or
   segmented-control internals depending on version.  Cover the semantic roles as
   well as the current data-testid hooks so the minimum target survives upgrades. */
.stButton > button,
div[data-testid="stPills"] button,
div[data-testid="stSegmentedControl"] button,
[role="button"],
[role="tab"],
[role="radio"] {
  min-height:44px;
}

/* Source links are evidence-bearing controls, not decorative text.  Preserve a
   non-colour affordance so they remain identifiable when colour perception or
   display contrast is limited. */
.source-card a,
.evidence-source-card a,
.reading-box a,
.detail-shell a {
  text-decoration:underline;
  text-decoration-thickness:.08em;
  text-underline-offset:.16em;
}

@media(max-width:760px){
  /* 48px is intentionally slightly larger than the desktop minimum because ALAM is
     phone-first and primary actions are frequently used one-handed. */
  .stButton > button,
  div[data-testid="stPills"] button,
  div[data-testid="stSegmentedControl"] button,
  [role="button"],
  [role="tab"],
  [role="radio"] {
    min-height:48px !important;
  }
}

/* The moving day atmosphere is optional presentation.  Respect the operating
   system's reduced-motion preference without removing content or changing the
   information hierarchy.  Very small non-zero durations avoid browser edge cases
   where an animation declaration with exactly zero duration is restarted. */
@media(prefers-reduced-motion:reduce){
  html:focus-within { scroll-behavior:auto !important; }
  *, *::before, *::after {
    animation-duration:.01ms !important;
    animation-iteration-count:1 !important;
    transition-duration:.01ms !important;
    transition-delay:0ms !important;
  }
}
</style>
"""


def install_accessibility() -> None:
    """Install accessibility safeguards after all feature/brand style layers.

    This is intentionally a rendering-only function with no session or backend
    reads, so it cannot add Supabase queries or change ALAM's fallback behavior.
    """

    st.markdown(ACCESSIBILITY_CSS, unsafe_allow_html=True)
