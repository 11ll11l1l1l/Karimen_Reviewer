"""Deterministic, evidence-only Ask ALAM retrieval over validated records."""
from __future__ import annotations
import json, re
from collections import OrderedDict
from urllib.parse import urlparse
import streamlit as st

CATEGORY_LABELS={"discover":"Discover","practical":"Action","reflection":"Market","trend":"Trends"}
ALIASES={"visa":("immigration","residence","在留","renewal"),"renew":("renewal","residence","在留"),"pr":("permanent residence","永住"),"tax":("tax","year-end","deduction","税","扶養"),"dependent":("dependent","扶養","spouse","relative"),"earthquake":("earthquake","seismic","plate","地震"),"quake":("earthquake","seismic","plate","地震"),"nisa":("nisa","investment","fund"),"yen":("yen","jpy","円","usd/jpy"),"market":("market","nikkei","topix","jgb","usd/jpy"),"scam":("scam","fraud","詐欺"),"benefit":("benefit","allowance","support","給付","手当")}
STOPWORDS={"a","an","and","are","as","at","be","can","do","does","for","from","how","i","in","is","it","me","my","of","on","or","should","the","this","to","what","when","where","which","who","why","with","yung","ang","ano","ba","ko","mo","sa","ng"}
TOKEN_RE=re.compile(r"[a-z0-9]+(?:[./-][a-z0-9]+)*|[\u3040-\u30ff\u3400-\u9fff]+",re.I)
SCORE_LABELS={"VERY HIGH":90.0,"HIGH":80.0,"MEDIUM-HIGH":70.0,"MED-HIGH":70.0,"MEDIUM":55.0,"MED":55.0,"LOW-MEDIUM":40.0,"LOW":30.0,"VERY LOW":15.0}
ASK_CSS=r'''<style>
.ask-shell{padding:16px 17px;margin:8px 0 14px;border:1px solid rgba(23,32,42,.09);border-radius:18px;background:rgba(255,255,255,.72)}
.ask-kicker{font-size:.68rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#667085}.ask-answer{font-size:1.02rem;line-height:1.55;font-weight:720;color:#273142;margin-top:7px}.ask-meta{font-size:.72rem;color:#667085;margin-top:8px;line-height:1.4}.ask-lens,.ask-perspective{padding:10px 11px;border:1px solid rgba(23,32,42,.08);border-radius:14px;margin:7px 0;background:rgba(255,255,255,.58)}.ask-lens strong,.ask-perspective strong{font-size:.78rem}.ask-lens span,.ask-perspective span{font-size:.78rem;color:#475467;line-height:1.45}.ask-stance{font-size:.64rem;font-weight:850;letter-spacing:.05em;color:#667085}
@media(max-width:760px){.ask-shell{padding:13px 13px;border-radius:16px}.ask-answer{font-size:.94rem}}
</style>'''

def _flat_text(value):
    if value is None:return ""
    if isinstance(value,str):return value
    try:return json.dumps(value,ensure_ascii=False,sort_keys=True)
    except (TypeError,ValueError):return str(value)

def _bounded_score(value):
    if isinstance(value,bool):return 100.0 if value else 0.0
    if isinstance(value,(int,float)):return max(0.0,min(100.0,float(value)))
    if isinstance(value,dict):
        for key in ("score","value","percent","percentage","rating"):
            if key in value:return _bounded_score(value.get(key))
        return 0.0
    text=str(value or "").strip().upper()
    if text in SCORE_LABELS:return SCORE_LABELS[text]
    match=re.search(r"-?\d+(?:\.\d+)?",text.replace(",",""))
    if not match:return 0.0
    try:return max(0.0,min(100.0,float(match.group(0))))
    except ValueError:return 0.0

def _display_score(value):
    """Render v5 score shapes consistently instead of leaking raw dicts/labels into UI metadata."""
    return f"{_bounded_score(value):g}"

def _search_fields(record):
    return {"title":str(record.get("title") or "").lower(),"tags":" ".join(str(x) for x in (record.get("tags") or [])).lower(),"summary":" ".join([str(record.get("summary") or ""),str(record.get("why_it_matters") or "")]).lower(),"body":" ".join([_flat_text(record.get("content")),_flat_text(record.get("claims")),_flat_text(record.get("geography"))]).lower()}

def _base_terms(query):return [t.lower() for t in TOKEN_RE.findall(str(query or "")) if len(t)>1 and t.lower() not in STOPWORDS]
def query_terms(query):
    ordered=OrderedDict()
    for token in _base_terms(query):
        ordered[token]=None
        for alias in ALIASES.get(token,()):ordered[alias.lower()]=None
    return list(ordered)

def relevance_score(record,query):
    terms=query_terms(query)
    if not terms:return 0.0
    fields,phrase,score,matched_core,core=_search_fields(record),str(query or "").strip().lower(),0.0,0,set(_base_terms(query))
    if len(phrase)>=4:
        if phrase in fields["title"]:score+=10
        elif phrase in fields["summary"]:score+=5
        elif phrase in fields["body"]:score+=2
    for term in terms:
        hit=False
        if term in fields["title"]:score+=5;hit=True
        if term in fields["tags"]:score+=3.5;hit=True
        if term in fields["summary"]:score+=2.5;hit=True
        if term in fields["body"]:score+=1;hit=True
        if hit and term in core:matched_core+=1
    if core and matched_core==0:return 0.0
    if score<=0:return 0.0
    importance=_bounded_score(record.get("importance") if record.get("importance") is not None else record.get("importance_score"));confidence=_bounded_score(record.get("confidence") if record.get("confidence") is not None else record.get("confidence_score"))
    return round(score+importance/100+confidence/200,4)

def filter_excluded_records(records,excluded_ids):
    """Remove exact recovery-story IDs before ranking so unresolved actions cannot repeat themselves."""
    excluded={str(value) for value in (excluded_ids or []) if value is not None and str(value)}
    if not excluded:return [record for record in (records or []) if isinstance(record,dict)]
    return [record for record in (records or []) if isinstance(record,dict) and str(record.get("id") or "") not in excluded]

def rank_records(records,query,limit=8):
    ranked=[]
    for record in records or []:
        if isinstance(record,dict) and record.get("id"):
            score=relevance_score(record,query)
            if score>0:ranked.append((score,record))
    ranked.sort(key=lambda item:(-item[0],str(item[1].get("id") or "")))
    return ranked[:max(1,int(limit))]

def grounded_answer(record):
    content=record.get("content") if isinstance(record.get("content"),dict) else {};reading=content.get("reading_levels") if isinstance(content.get("reading_levels"),dict) else {};short=reading.get("30 sec") if isinstance(reading.get("30 sec"),dict) else {}
    for candidate in (content.get("key_message"),short.get("bottom_line"),short.get("what_happened"),record.get("summary")):
        text=str(candidate or "").strip()
        if text:return text
    return ""

def grounded_next_step(record):
    content=record.get("content") if isinstance(record.get("content"),dict) else {};reading=content.get("reading_levels") if isinstance(content.get("reading_levels"),dict) else {};short=reading.get("30 sec") if isinstance(reading.get("30 sec"),dict) else {};action_plan=content.get("action_plan") if isinstance(content.get("action_plan"),dict) else {}
    for candidate in (short.get("what_to_do_watch"),content.get("recommendation"),action_plan.get("goal"),content.get("what_next")):
        text=str(candidate or "").strip()
        if text:return text
    return ""

def grounded_sources(record,limit=3):
    output,seen=[],set()
    for source in record.get("sources") or []:
        if not isinstance(source,dict):continue
        url=str(source.get("url") or "").strip();parsed=urlparse(url)
        if parsed.scheme not in {"http","https"} or not parsed.netloc or url in seen:continue
        seen.add(url);publisher=str(source.get("publisher") or parsed.netloc).strip();title=str(source.get("title") or publisher or parsed.netloc).strip()
        output.append({"publisher":publisher,"title":title,"url":url,"source_type":str(source.get("source_type") or "").strip()})
        if len(output)>=max(1,int(limit)):break
    return output

def grounded_perspectives(comments,story_id,limit=3):
    """Return substantive current-story perspectives, challenge-first, without inventing debate."""
    valid=[]
    for comment in comments or []:
        if not isinstance(comment,dict) or str(comment.get("story_id") or "")!=str(story_id or ""):continue
        body=str(comment.get("body") or "").strip();stance=str(comment.get("stance") or "MIXED").upper().strip()
        if not body or stance not in {"SUPPORT","CHALLENGE","MIXED"}:continue
        valid.append({"stance":stance,"body":body,"persona":str(comment.get("persona_id") or comment.get("agent") or "ALAM agent").replace("-"," ").title(),"created_at":str(comment.get("created_at") or "")})
    priority={"CHALLENGE":0,"MIXED":1,"SUPPORT":2}
    valid.sort(key=lambda item:(priority[item["stance"]],item["created_at"],item["persona"]))
    return valid[:max(1,int(limit))]

def _record_lens(record):return CATEGORY_LABELS.get(str(record.get("_category") or record.get("category") or ""),"ALAM")
def _compact_record_line(record):
    text=grounded_answer(record) or str(record.get("summary") or "").strip()
    return text[:237].rstrip()+"..." if len(text)>240 else text

def render_ask_alam(records,comments,manager,views):
    st.markdown(ASK_CSS,unsafe_allow_html=True)
    st.markdown('<div class="hero mobile-hero"><div class="hero-kicker">✦ ASK ALAM · GROUNDED BETA</div><div class="hero-title">Ask the verified corpus.</div><div class="hero-copy">ALAM answers only when its screened agent records support the question. No model-memory fallback.</div></div>',unsafe_allow_html=True)
    source_mode=str(st.session_state.get("alam_content_source") or "").strip();source_label="live Supabase corpus" if source_mode=="supabase" else "validated audit fallback"
    st.caption(f"Evidence source: {source_label}. Your question text is used locally for retrieval and is not stored by this feature.")
    query=st.text_input("Ask ALAM",placeholder="e.g. What changes for my visa renewal in October?",key="alam_ask_query")
    lenses=st.multiselect("Agent lenses",["Discover","Action","Market","Trends"],default=[],placeholder="All verified lenses",key="alam_ask_lenses")
    category_by_label={value:key for key,value in CATEGORY_LABELS.items()};allowed={category_by_label[label] for label in lenses if label in category_by_label};pool=[r for r in filter_excluded_records(records,st.session_state.get("alam_ask_excluded_story_ids")) if not allowed or str(r.get("_category") or r.get("category") or "") in allowed]
    if not str(query or "").strip():st.info("Try a real question about Japan paperwork, household money, safety, markets, technology, or a topic ALAM has already researched.");return
    ranked=rank_records(pool,query,limit=8)
    if not ranked:st.warning("INSUFFICIENT ALAM EVIDENCE — I found no screened current record that directly supports this question. Try broader wording or wait for the research agents to cover it.");return
    top_score,top=ranked[0];answer=grounded_answer(top)
    if not answer:st.warning("A relevant record exists, but it has no safe reader-facing answer sentence to reuse yet.");return
    confidence=top.get("confidence") if top.get("confidence") is not None else top.get("confidence_score");importance=top.get("importance") if top.get("importance") is not None else top.get("importance_score");meta=[f"{_record_lens(top)} agent",f"retrieval score {top_score:.1f}"]
    if confidence is not None:meta.append(f"record confidence {_display_score(confidence)}/100")
    if importance is not None:meta.append(f"importance {_display_score(importance)}/100")
    st.markdown('<div class="ask-shell"><div class="ask-kicker">Grounded answer</div>'+f'<div class="ask-answer">{_escape(answer)}</div><div class="ask-meta">{" · ".join(_escape(x) for x in meta)}</div></div>',unsafe_allow_html=True)
    next_step=grounded_next_step(top)
    if next_step:st.markdown("**What to do / watch**");st.write(next_step)
    citations=grounded_sources(top)
    if citations:
        st.markdown("**Sources behind this answer**")
        for source in citations:
            badge=" · official" if source.get("source_type") in {"official","primary"} else ""
            st.link_button(f"{source['publisher']}{badge} — {source['title']}",source["url"],use_container_width=True)
    perspectives=grounded_perspectives(comments,top.get("id"),limit=3)
    if perspectives:
        st.markdown("**Where ALAM agrees or pushes back**")
        st.caption("These are existing agent perspectives attached to the same verified story—not a debate generated for your question.")
        for item in perspectives:
            st.markdown(f'<div class="ask-perspective"><div class="ask-stance">{_escape(item["stance"])} · {_escape(item["persona"])}</div><span>{_escape(item["body"])}</span></div>',unsafe_allow_html=True)
    by_lens=OrderedDict()
    for _,record in ranked:
        lens=_record_lens(record)
        if lens not in by_lens:by_lens[lens]=record
    if len(by_lens)>1:
        st.markdown("**Cross-agent evidence**")
        for lens,record in by_lens.items():st.markdown(f'<div class="ask-lens"><strong>{_escape(lens)}</strong><br><span>{_escape(_compact_record_line(record))}</span></div>',unsafe_allow_html=True)
    st.markdown("**Open the evidence**");cols=st.columns(2,wrap=True)
    for index,(_,record) in enumerate(ranked[:6]):
        with cols[index%2]:views.render_card(record,f"ask_alam_{index}",manager,comments)
    st.caption("Ask ALAM performs deterministic evidence retrieval, exposes direct sources and existing same-story agent challenges, and refuses unsupported answers. No model-memory fallback.")

def _escape(value):
    return str(value or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#x27;")
