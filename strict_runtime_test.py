from __future__ import annotations
import importlib.util, sys, types
from pathlib import Path

class StopExecution(Exception): pass
class RerunExecution(Exception): pass

class StrictSessionState(dict):
    def __init__(self):
        super().__init__(); self.widget_keys=set(); self.widget_write=False
    def __getattr__(self,k):
        try:return self[k]
        except KeyError: raise AttributeError(k)
    def __setattr__(self,k,v):
        if k in {'widget_keys','widget_write'}: return object.__setattr__(self,k,v)
        self.__setitem__(k,v)
    def __setitem__(self,k,v):
        if k in getattr(self,'widget_keys',set()) and not getattr(self,'widget_write',False):
            raise RuntimeError(f'Illegal direct mutation of instantiated widget key: {k}')
        return super().__setitem__(k,v)
    def widget_set(self,k,v):
        object.__setattr__(self,'widget_write',True)
        try: super().__setitem__(k,v)
        finally: object.__setattr__(self,'widget_write',False)
        self.widget_keys.add(k)
    def new_run(self):
        self.widget_keys.clear()

class Proxy:
    def __init__(self,st): self.st=st
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def _widget(self,key,val):
        if key is not None:
            cur=self.st.session_state.get(key,val)
            self.st.session_state.widget_set(key,cur)
            return cur
        return val
    def markdown(self,*a,**k): pass
    def image(self,*a,**k): pass
    def caption(self,*a,**k): pass
    def info(self,*a,**k): pass
    def success(self,*a,**k): pass
    def warning(self,*a,**k): pass
    def error(self,*a,**k): pass
    def code(self,*a,**k): pass
    def write(self,*a,**k): pass
    def metric(self,*a,**k): pass
    def progress(self,*a,**k): pass
    def dataframe(self,*a,**k): pass
    def bar_chart(self,*a,**k): pass
    def line_chart(self,*a,**k): pass
    def bar_chart(self,*a,**k): pass
    def line_chart(self,*a,**k): pass
    def audio(self,*a,**k): pass
    def button(self,*a,key=None,**k): return self._widget(key,False)
    def download_button(self,*a,key=None,**k): return self._widget(key,False)
    def form_submit_button(self,*a,key=None,**k): return self._widget(key,False)
    def file_uploader(self,*a,key=None,**k): return self._widget(key,None)
    def checkbox(self,*a,value=False,key=None,**k): return self._widget(key,value)
    def text_input(self,*a,value='',key=None,**k): return self._widget(key,value)
    def selectbox(self,label,options,index=0,key=None,**k):
        opts=list(options); val=opts[index] if opts else None
        if key is not None and self.st.session_state.get(key,val) not in opts:
            self.st.session_state.pop(key,None)
        return self._widget(key,val)
    def radio(self,label,options,index=0,key=None,**k): return self.selectbox(label,options,index,key,**k)
    def number_input(self,*a,value=0,key=None,**k): return self._widget(key,value)
    def slider(self,*a,value=None,key=None,**k):
        if value is None: value=a[3] if len(a)>3 else (a[1] if len(a)>1 else 0)
        return self._widget(key,value)

class FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__('streamlit'); self.__path__=[]; self.session_state=StrictSessionState(); self.secrets={}; self._p=Proxy(self)
    def set_page_config(self,*a,**k): pass
    def deco(self,*a,**k):
        if a and callable(a[0]) and len(a)==1 and not k:return a[0]
        return lambda f:f
    cache_data=deco; cache_resource=deco; fragment=deco
    def columns(self,spec,*a,**k): return [Proxy(self) for _ in range(spec if isinstance(spec,int) else len(spec))]
    def expander(self,*a,**k): return Proxy(self)
    def form(self,*a,**k): return Proxy(self)
    def __getattr__(self,name): return getattr(self._p,name)
    def stop(self): raise StopExecution()
    def rerun(self,*a,**k): raise RerunExecution()
    def balloons(self): pass

st=FakeStreamlit(); sys.modules['streamlit']=st
comp=types.ModuleType('streamlit.components.v1'); comp.html=lambda *a,**k:None
pkg=types.ModuleType('streamlit.components'); pkg.__path__=[]; pkg.v1=comp
sys.modules['streamlit.components']=pkg; sys.modules['streamlit.components.v1']=comp
root=Path(__file__).resolve().parent; sys.path.insert(0,str(root))

def load(name):
    st.session_state.new_run()
    spec=importlib.util.spec_from_file_location(name,root/'app.py'); mod=importlib.util.module_from_spec(spec)
    try: spec.loader.exec_module(mod)
    except StopExecution: pass
    return mod

# First/profile page.
app=load('strict_profile')
assert st.session_state['profile_ready'] is False

# Main routes with stable widget state.
st.session_state.widget_keys.clear()
st.session_state['profile_ready']=True
st.session_state['player_name']='Tester'
st.session_state['avatar']='🐱'
st.session_state['bank_scope']='Karimen'
st.session_state['voice_mode']='Off'; st.session_state['opt_voice']=False
for route in ['Home','Play','Mistakes','Progress','Rankings','Bank']:
    st.session_state.widget_keys.clear()
    st.session_state['route']=route; st.session_state['nav_choice']=route; st.session_state['sync_nav']=False
    load('strict_'+route.lower())
print('STRICT_RUNTIME_OK')

# Direct game-state checks under the same strict Streamlit semantics.
st.session_state.widget_keys.clear()
st.session_state['route']='Home'; st.session_state['nav_choice']='Home'; st.session_state['sync_nav']=False
app=load('strict_game_logic')
assert app.launch_smart() and st.session_state.review and st.session_state.review['ids']
assert all(app.BY_ID[qid]['bank']=='Karimen' for qid in st.session_state.review['ids'])
q=app.BY_ID[st.session_state.review['ids'][0]]
# Two wrong answers should move the mascot into a pleading state; a recovery should become comeback.
wrong_choice = not bool(q['answer'])
before_len = len(st.session_state.review['ids'])
app.answer_review(q, wrong_choice)
assert st.session_state.review_feedback['ok'] is False
assert st.session_state.review_feedback.get('retry_queued') is True
assert len(st.session_state.review['ids']) == before_len + 1
st.session_state.review_feedback=None
st.session_state.review_started_at=__import__('time').time()
app.answer_review(q, wrong_choice)
assert st.session_state.review_feedback['state'] in {'pleading','double_wrong'}
st.session_state.review_feedback=None
st.session_state.review_started_at=__import__('time').time()
app.answer_review(q, bool(q['answer']))
assert st.session_state.review_feedback['state']=='comeback'

assert app.launch_daily() and len(st.session_state.review['ids'])==10
assert all(app.BY_ID[qid]['bank']=='Karimen' for qid in st.session_state.review['ids'])
assert app.launch_survival() and st.session_state.review['lives']==3
# Lose all three lives deterministically.
for _ in range(3):
    q=app.BY_ID[st.session_state.review['ids'][st.session_state.review['index']]]
    st.session_state.review_feedback=None
    st.session_state.review_started_at=__import__('time').time()
    app.answer_review(q, not bool(q['answer']))
assert st.session_state.review['finished'] is True and st.session_state.review['lives']==0

assert app.start_exam(count=50, minutes=30)
exam=st.session_state.exam
assert len(exam['ids'])==50 and all(app.BY_ID[qid]['bank']=='Karimen' for qid in exam['ids'])
# Submit a perfect deterministic mock exam to exercise scoring and result state.
exam['answers']={qid: bool(app.BY_ID[qid]['answer']) for qid in exam['ids']}
app.submit_exam()
assert exam['submitted'] is True and exam['correct']==50
print('STRICT_GAME_STATE_OK')

# v4.4 additions: saved rules, confidence, skip, and resume.
st.session_state.widget_keys.clear()
st.session_state['review']=None; st.session_state['review_feedback']=None; st.session_state['exam']=None; st.session_state['active_game']=None
first_a1 = next(q for q in app.QUESTIONS if q['bank']=='Karimen')
assert app.toggle_bookmark(st.session_state.progress, first_a1['id']) is True
assert app.is_bookmarked(st.session_state.progress, first_a1['id'])
assert app.bookmark_count() >= 1
assert app.launch_bookmarks()
assert first_a1['id'] in st.session_state.review['ids']
# Skip should rotate the current question without scoring an attempt.
ids = [q['id'] for q in app.active_questions()[:3]]
assert app.start_review(ids.copy(), 'Skip test')
old_first = st.session_state.review['ids'][0]
assert app.skip_review_current() is True
assert st.session_state.review['answered'] == 0
assert st.session_state.review['ids'][-1] == old_first
# Confidence tagging must not change score and guessed questions become drillable.
q = app.BY_ID[st.session_state.review['ids'][0]]
st.session_state.review_feedback=None
app.answer_review(q, bool(q['answer']))
before_attempts = app.qstat(q['id'])['attempts']
app.record_confidence(st.session_state.progress, q['id'], True, True)
assert app.qstat(q['id'])['attempts'] == before_attempts
assert app.qstat(q['id'])['confidence_guessed'] >= 1
st.session_state['review']=None; st.session_state['review_feedback']=None; st.session_state['active_game']=None
assert app.launch_guessed() and q['id'] in st.session_state.review['ids']
# Browsing away must leave an active run resumable.
st.session_state['review']=None; st.session_state['review_feedback']=None; st.session_state['active_game']=None
assert app.start_exam(count=5, minutes=10)
st.session_state['active_game']=None
pending = app.resumable_game()
assert pending and pending[0]=='exam'
print('V44_FEATURES_OK')
