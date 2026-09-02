"""Mobile shell hardening and compact runtime presentation for ALAM.ph.

This module fixes first-render layout shift from the CookieManager custom component,
keeps the mobile navigation clear of story content, and compresses the persistent
header/briefing chrome so useful intelligence appears much earlier on small screens.
It intentionally changes presentation only; content, ranking, Supabase reads and
browser-local state contracts remain owned by their existing modules.
"""

from __future__ import annotations

import streamlit as st


COOKIE_GUARD_CSS = r"""
<style>
/* CookieManager is a real iframe-backed Streamlit component. Keep it mounted so its
   JavaScript can read/write cookies, but remove it from document flow so mobile first
   render cannot reserve hundreds of blank pixels before the ALAM brand appears. */
.st-key-alam_cookie_host{
  position:absolute!important;
  width:1px!important;
  height:1px!important;
  min-height:0!important;
  max-height:1px!important;
  margin:0!important;
  padding:0!important;
  overflow:hidden!important;
  opacity:0!important;
  pointer-events:none!important;
}
.st-key-alam_cookie_host [data-testid="stCustomComponentV1"],
.st-key-alam_cookie_host iframe{
  width:1px!important;
  height:1px!important;
  min-height:0!important;
  max-height:1px!important;
  margin:0!important;
  padding:0!important;
  border:0!important;
  overflow:hidden!important;
}
</style>
"""


MOBILE_SHELL_CSS = r"""
<style>
/* Runtime status is informational, not the hero. */
.alam-runtime-status{
  display:inline-flex!important;
  width:auto!important;
  max-width:100%!important;
  align-items:center!important;
  gap:6px!important;
  border-radius:999px!important;
  padding:5px 9px!important;
  margin:-1px 0 7px!important;
  font-size:.66rem!important;
  line-height:1.2!important;
  box-shadow:none!important;
}
.alam-runtime-status .alam-runtime-dot{margin-top:0!important;width:6px!important;height:6px!important}

@media(max-width:760px){
  /* First screen: spend pixels on intelligence, not scaffolding. */
  .block-container{
    padding-top:.34rem!important;
    padding-left:.86rem!important;
    padding-right:.86rem!important;
    padding-bottom:6.25rem!important;
  }
  .alam-brand{padding:2px 0 6px!important;gap:10px!important}
  .alam-logo{font-size:1.52rem!important;line-height:1!important}
  .alam-logo span{font-size:.61rem!important;margin:.10rem 0 0!important}
  .live-pill{padding:5px 8px!important;font-size:.63rem!important;gap:5px!important}
  .live-dot{width:6px!important;height:6px!important;box-shadow:0 0 0 3px rgba(8,125,91,.10)!important}

  /* Preserve the time-of-day identity at roughly half the old mobile height. */
  .alam-time-header{
    min-height:82px!important;
    padding:10px 13px!important;
    border-radius:15px!important;
    margin:0 0 7px!important;
    box-shadow:0 8px 22px rgba(23,32,42,.10)!important;
  }
  .alam-time-header-kicker{font-size:.56rem!important;letter-spacing:.09em!important}
  .alam-time-header-title{font-size:1.02rem!important;margin-top:1px!important}
  .alam-time-header-sub{
    font-size:.68rem!important;
    line-height:1.25!important;
    margin-top:2px!important;
    max-width:92%!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
  }

  /* Daily Bible + Taglish reflection stays first-class but compact. */
  .wisdom-strip{
    margin:0 0 7px!important;
    padding:7px 9px!important;
    border-radius:12px!important;
  }
  .wisdom-verse{font-size:.63rem!important;line-height:1.28!important}
  .wisdom-verse:nth-of-type(n+2){display:none!important}
  .wisdom-question{
    font-size:.72rem!important;
    line-height:1.32!important;
    margin-top:4px!important;
  }

  /* A true mobile bottom nav: low in the viewport with reserved content space.
     The old 3.65rem offset made the bar float over feed content on Android browsers. */
  .st-key-main_nav{
    position:fixed!important;
    top:auto!important;
    bottom:calc(.55rem + env(safe-area-inset-bottom, 0px))!important;
    left:50%!important;
    transform:translateX(-50%)!important;
    width:calc(100% - 1.1rem)!important;
    max-width:680px!important;
    z-index:1001!important;
    margin:0!important;
    padding:.25rem!important;
    border:1px solid rgba(23,32,42,.10)!important;
    border-radius:16px!important;
    background:rgba(245,244,240,.97)!important;
    box-shadow:0 9px 26px rgba(23,32,42,.15)!important;
    backdrop-filter:blur(16px)!important;
    -webkit-backdrop-filter:blur(16px)!important;
  }
  .st-key-main_nav button{
    min-height:36px!important;
    padding:.25rem .28rem!important;
    font-size:.72rem!important;
  }

  /* "Today in 3 lines" should literally behave like three compact lines. */
  .intel-title{margin:5px 0 4px!important;font-size:.66rem!important}
  .intel-brief-grid{
    display:grid!important;
    grid-template-columns:1fr!important;
    gap:4px!important;
    margin:0 0 8px!important;
  }
  .intel-brief-card{
    display:grid!important;
    grid-template-columns:52px minmax(0,1fr)!important;
    align-items:center!important;
    column-gap:6px!important;
    padding:7px 9px!important;
    border-radius:12px!important;
  }
  .intel-kicker{grid-column:1!important;font-size:.58rem!important}
  .intel-brief-head{
    grid-column:2!important;
    margin:0!important;
    font-size:.76rem!important;
    line-height:1.22!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
  }
  .intel-brief-copy,.intel-mini{display:none!important}
  .intel-alert{
    padding:6px 8px!important;
    margin:3px 0 6px!important;
    border-radius:11px!important;
    font-size:.68rem!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
  }
  .intel-alert span{display:none!important}

  /* Empty intent lanes are useful diagnostics on desktop but waste the phone's first
     screen. Hide only empty lanes; any real DO/PREPARE/AVOID/WATCH item remains. */
  .today-priority-title{font-size:.98rem!important;margin:10px 0 2px!important}
  .today-priority-copy{font-size:.69rem!important;margin-bottom:6px!important}
  .today-action-grid{grid-template-columns:1fr!important;gap:6px!important;margin:5px 0 9px!important}
  .today-action-card{padding:9px 10px!important;border-radius:13px!important}
  .today-action-card:has(.today-empty){display:none!important}
  .today-action-head{font-size:.82rem!important;margin-top:3px!important}
  .today-action-body{font-size:.70rem!important;line-height:1.34!important;margin-top:4px!important}
  .today-action-meta{font-size:.59rem!important;margin-top:5px!important}
  .today-discover-head{margin:12px 0 6px!important}

  /* Prevent generic heroes in secondary pages from reverting to desktop-scale cards. */
  .hero.mobile-hero{padding:16px!important;border-radius:19px!important;margin-bottom:11px!important}
  .hero.mobile-hero .hero-title{font-size:1.55rem!important;margin-bottom:7px!important}
  .hero.mobile-hero .hero-copy{font-size:.86rem!important;line-height:1.45!important}
}
</style>
"""


def install_cookie_guard():
    """Install the zero-layout CookieManager host rules before the component mounts."""
    st.markdown(COOKIE_GUARD_CSS, unsafe_allow_html=True)


def install_mobile_shell():
    """Install compact mobile presentation after persisted display settings load."""
    st.markdown(MOBILE_SHELL_CSS, unsafe_allow_html=True)


def render_runtime_status():
    """Render a small feed-source chip; keep fallback explanation collapsed."""
    source = st.session_state.get("alam_content_source")
    if source == "supabase":
        st.markdown(
            '<div class="alam-runtime-status live"><span class="alam-runtime-dot"></span>'
            '<div><strong>Supabase live</strong> · current feed</div></div>',
            unsafe_allow_html=True,
        )
    elif source == "local_fallback":
        st.markdown(
            '<div class="alam-runtime-status fallback"><span class="alam-runtime-dot"></span>'
            '<div><strong>Safe fallback</strong> · verified GitHub copy</div></div>',
            unsafe_allow_html=True,
        )
        with st.expander("Why is fallback active?", expanded=False):
            st.caption(
                "ALAM could not use a current populated Supabase feed for this session, "
                "so it is serving the verified GitHub audit copy. Reading remains safe, "
                "but database-backed cross-device features may be incomplete until sync recovers."
            )
