from __future__ import annotations
import importlib.util, sys, types
from pathlib import Path

class StopExecution(Exception): pass
class SessionState(dict):
    __getattr__=dict.get
    def __setattr__(self,k,v): self[k]=v
class Proxy:
    def __init__(self,st): self.st=st
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def __getattr__(self,name):
        if name in {'button','download_button','form_submit_button'}: return lambda *a,**k: False
        if name=='file_uploader': return lambda *a,**k: None
        if name=='checkbox': return lambda *a,value=False,key=None,**k: self._state(key,value)
        if name=='text_input': return lambda *a,value='',key=None,**k: self._state(key,value)
        if name in {'selectbox','radio'}: return lambda label,options,index=0,key=None,**k: self._select(options,index,key)
        if name=='number_input': return lambda *a,value=0,**k:value
        if name=='slider': return lambda *a,value=20,**k:value
        return lambda *a,**k: None
    def _state(self,key,val):
        if key is not None:self.st.session_state.setdefault(key,val); return self.st.session_state[key]
        return val
    def _select(self,options,index,key):
        options=list(options); val=options[index] if options else None
        if key is not None:
            cur=self.st.session_state.get(key,val)
            if cur not in options:cur=val
            self.st.session_state[key]=cur
            return cur
        return val
class FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__('streamlit'); self.__path__=[]; self.session_state=SessionState(profile_ready=True,player_name='Tester',avatar='🐱',bank_scope='A1',route='Rankings',nav_choice='Rankings',sync_nav=False); self.secrets={'SUPABASE_URL':'https://example.supabase.co','SUPABASE_SECRET_KEY':'secret'}
    def set_page_config(self,*a,**k):pass
    def deco(self,*a,**k):
        if a and callable(a[0]) and len(a)==1 and not k:return a[0]
        return lambda f:f
    cache_data=deco; cache_resource=deco; fragment=deco
    def columns(self,spec,*a,**k): return [Proxy(self) for _ in range(spec if isinstance(spec,int) else len(spec))]
    def expander(self,*a,**k): return Proxy(self)
    def form(self,*a,**k): return Proxy(self)
    def __getattr__(self,name): return getattr(Proxy(self),name)
    def stop(self): raise StopExecution
    def rerun(self): raise RuntimeError('unexpected rerun')

class Query:
    def __init__(self,db,table): self.db=db; self.table_name=table; self.op='select'; self.payload=None; self.filters=[]; self.limit_n=None
    def select(self,*a,**k): self.op='select'; return self
    def limit(self,n): self.limit_n=n; return self
    def eq(self,*a,**k): self.filters.append(('eq',a)); return self
    def gte(self,*a,**k): self.filters.append(('gte',a)); return self
    def order(self,*a,**k): return self
    def upsert(self,payload,**k): self.op='upsert'; self.payload=payload; self.db.upserts.append((self.table_name,payload)); return self
    def insert(self,payload,**k): self.op='insert'; self.payload=payload; self.db.inserts.append((self.table_name,payload)); return self
    def execute(self):
        data=list(self.db.data.get(self.table_name,[]))
        if self.table_name=='live_exams':
            for kind,args in self.filters:
                if kind=='eq' and args[0]=='status': data=[r for r in data if r.get('status')==args[1]]
        if self.limit_n is not None:data=data[:self.limit_n]
        return types.SimpleNamespace(data=data)
class DB:
    def __init__(self):
        self.upserts=[]; self.inserts=[]
        self.data={
          'live_exams':[{'session_id':'s1','display_name':'Live','avatar':'🚙','bank':'A1','set_label':'All','total_questions':50,'answered':10,'correct':9,'started_at':'2026-08-22T00:00:00+00:00','last_seen':'2026-08-22T07:00:00+00:00','status':'active'}],
          'exam_results':[{'id':1,'session_id':'x','display_name':'Winner','avatar':'🐱','bank':'A1','set_label':'All','score':49,'total_questions':50,'percent':98.0,'elapsed_seconds':800,'passed':True,'completed_at':'2026-08-22T06:00:00+00:00'}]
        }
    def table(self,name): return Query(self,name)
DBI=DB()
supa=types.ModuleType('supabase'); supa.create_client=lambda url,key: DBI; sys.modules['supabase']=supa
st=FakeStreamlit(); sys.modules['streamlit']=st
comp=types.ModuleType('streamlit.components.v1'); comp.html=lambda *a,**k:None
pkg=types.ModuleType('streamlit.components'); pkg.__path__=[]; pkg.v1=comp
st.components=pkg
sys.modules['streamlit.components']=pkg; sys.modules['streamlit.components.v1']=comp
root=Path(__file__).resolve().parent; sys.path.insert(0,str(root))
spec=importlib.util.spec_from_file_location('app_supa_test',root/'app.py'); app=importlib.util.module_from_spec(spec); spec.loader.exec_module(app)
ok,msg=app.ranking_connection_state(); assert ok, msg
assert len(app.fetch_exam_results())==1
exam={'session_id':'new','ids':[app.active_questions()[0]['id']]*50,'answers':{},'started_iso':'2026-08-22T07:00:00+00:00','bank':'A1','set':'All','correct':45,'elapsed':600,'online_saved':False}
app.sync_live_exam(exam)
assert DBI.upserts and DBI.upserts[-1][0]=='live_exams'
app.save_online_result(exam)
assert any(t=='exam_results' for t,_ in DBI.upserts)
assert exam['online_saved'] is True
print('SUPABASE_STUB_OK')
# v4.3 must reject anon/publishable credentials instead of showing false green.
st.secrets['SUPABASE_SECRET_KEY']='sb_publishable_test'
st.session_state['ranking_diagnostic']=None
ok,msg=app.ranking_connection_state(force=True)
assert not ok and 'anon/publishable' in msg
st.secrets['SUPABASE_SECRET_KEY']='secret'
st.session_state['ranking_diagnostic']=None
ok,msg=app.ranking_connection_state(force=True)
assert ok, msg
assert any(t=='live_exams' and p.get('status')=='diagnostic' for t,p in DBI.upserts)
print('SUPABASE_PERMISSION_DIAGNOSTIC_OK')
