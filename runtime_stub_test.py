from __future__ import annotations
import importlib.util, sys, types
from pathlib import Path

class StopExecution(Exception): pass
class RerunExecution(Exception): pass

class SessionState(dict):
    def __getattr__(self,k):
        try:return self[k]
        except KeyError: raise AttributeError(k)
    def __setattr__(self,k,v): self[k]=v

class Proxy:
    def __init__(self, st): self.st=st
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def markdown(self,*a,**k): return None
    def image(self,*a,**k): return None
    def caption(self,*a,**k): return None
    def info(self,*a,**k): return None
    def success(self,*a,**k): return None
    def warning(self,*a,**k): return None
    def error(self,*a,**k): return None
    def code(self,*a,**k): return None
    def write(self,*a,**k): return None
    def metric(self,*a,**k): return None
    def progress(self,*a,**k): return None
    def dataframe(self,*a,**k): return None
    def button(self,*a,**k): return False
    def checkbox(self,label,value=False,key=None,**kw):
        if key is not None:
            if key not in self.st.session_state:self.st.session_state[key]=value
            return self.st.session_state[key]
        return value
    def text_input(self,label,value='',key=None,**kw):
        if key is not None:
            if key not in self.st.session_state:self.st.session_state[key]=value
            return self.st.session_state[key]
        return value
    def selectbox(self,label,options,index=0,key=None,format_func=None,**kw):
        options=list(options)
        val=options[index] if options else None
        if key is not None:
            cur=self.st.session_state.get(key,val)
            if cur not in options: cur=val
            self.st.session_state[key]=cur
            return cur
        return val
    def radio(self,label,options,index=0,key=None,**kw): return self.selectbox(label,options,index,key,**kw)
    def number_input(self,*a,value=0,**k): return value
    def slider(self,*a,value=None,**k):
        if value is not None:return value
        return a[3] if len(a)>3 else (a[1] if len(a)>1 else 0)

class FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__('streamlit'); self.session_state=SessionState(); self.secrets={}; self._proxy=Proxy(self)
    def set_page_config(self,*a,**k): pass
    def _decorator(self,*args,**kwargs):
        if args and callable(args[0]) and len(args)==1 and not kwargs:return args[0]
        return lambda f:f
    cache_data=_decorator; cache_resource=_decorator; fragment=_decorator
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
    def balloons(self): pass
    def columns(self,spec,*a,**k):
        n=spec if isinstance(spec,int) else len(spec)
        return [Proxy(self) for _ in range(n)]
    def expander(self,*a,**k): return Proxy(self)
    def form(self,*a,**k): return Proxy(self)
    def button(self,*a,**k): return False
    def form_submit_button(self,*a,**k): return False
    def checkbox(self,*a,**k): return Proxy(self).checkbox(*a,**k)
    def text_input(self,*a,**k): return Proxy(self).text_input(*a,**k)
    def selectbox(self,*a,**k): return Proxy(self).selectbox(*a,**k)
    def radio(self,*a,**k): return Proxy(self).radio(*a,**k)
    def number_input(self,*a,**k): return Proxy(self).number_input(*a,**k)
    def slider(self,*a,**k): return Proxy(self).slider(*a,**k)
    def download_button(self,*a,**k): return False
    def file_uploader(self,*a,**k): return None
    def stop(self): raise StopExecution()
    def rerun(self): raise RerunExecution()

fake=FakeStreamlit()
sys.modules['streamlit']=fake
components=types.ModuleType('streamlit.components.v1'); components.html=lambda *a,**k:None
comp_pkg=types.ModuleType('streamlit.components'); comp_pkg.v1=components
sys.modules['streamlit.components']=comp_pkg; sys.modules['streamlit.components.v1']=components

root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))

def load(name):
    spec=importlib.util.spec_from_file_location(name,root/'app.py'); mod=importlib.util.module_from_spec(spec)
    try:spec.loader.exec_module(mod)
    except StopExecution: pass
    return mod

# First page must stop before main app.
app=load('app_profile_test')
assert fake.session_state.get('profile_ready') is False
assert app.active_bank_scope()=='All'
assert len(app.active_questions())==650

# Simulate completed profile and reload main Home.
fake.session_state['profile_ready']=True
fake.session_state['player_name']='Tester'
fake.session_state['avatar']='🐱'
fake.session_state['bank_scope']='A1'
fake.session_state['route']='Home'; fake.session_state['nav_choice']='Home'; fake.session_state['sync_nav']=False
app2=load('app_main_test')
assert len(app2.active_questions())==150
assert all(q['bank']=='A1' for q in app2.active_questions())
assert app2.effective_bank('All')=='A1'
assert app2.filter_questions('B1')==[]
# Render non-game pages with inert widgets.
for fn in [app2.page_play, app2.page_mistakes, app2.page_progress, app2.page_rankings, app2.page_bank]:
    fn()
# B1 scope.
fake.session_state['bank_scope']='B1'
assert len(app2.active_questions())==500
assert all(q['bank']=='B1' for q in app2.active_questions())
# Leaderboard tie break: score first, then fastest.
board=app2.build_best_leaderboard([
 {'display_name':'A','avatar':'🐱','score':45,'total_questions':50,'percent':90,'elapsed_seconds':600,'passed':True},
 {'display_name':'A','avatar':'🐱','score':45,'total_questions':50,'percent':90,'elapsed_seconds':500,'passed':True},
 {'display_name':'B','avatar':'🚙','score':46,'total_questions':50,'percent':92,'elapsed_seconds':900,'passed':True},
])
assert board.iloc[0]['Examiner'].endswith('B')
assert board.iloc[1]['Time']=='8:20'
print('RUNTIME_STUB_OK')
