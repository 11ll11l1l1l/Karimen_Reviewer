from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


def workbook_sheets(path: str) -> list[str]:
    p=Path(path)
    if p.suffix.lower()=='.csv': return ['CSV']
    return list(pd.ExcelFile(path).sheet_names)


def read_table(path: str, sheet: str|int=0) -> pd.DataFrame:
    p=Path(path)
    if p.suffix.lower()=='.csv': return pd.read_csv(path)
    return pd.read_excel(path, sheet_name=sheet)


def _norm(s: Any) -> str:
    return re.sub(r'[^a-z0-9]+','_',str(s).strip().lower()).strip('_')


ALIASES={
'equipment_id':['equipment','equipment_id','eq_id','tool_id','machine_id','asset_id'],
'pm_id':['pm_id','pm_code','maintenance_id'], 'pm_name':['pm_name','pm','maintenance','activity_name'],
'original_due_date':['original_due','original_due_date','due_date','due'], 'scheduled_date':['scheduled','scheduled_date','plan_date'],
'last_completion_date':['last_completion','last_completion_date','last_pm','completed_date'], 'status':['status','state'],
'assigned_to':['assigned','assigned_to','owner','technician'], 'estimated_hours':['estimated_hours','hours','duration_hr','duration'],
'priority':['priority','prio'], 'deferral_reason':['deferral_reason','defer_reason','reason'], 'sop_path':['sop','sop_path'], 'report_path':['report','report_path'],
'step_no':['step','step_no','step_number','no'], 'activity':['activity','step_description','description','check_item','item'],
'method':['method','measurement_method'], 'spec':['spec','specification','criteria','acceptance'], 'unit':['unit','units'],
'warning_low':['warning_low','wl','warn_low'], 'warning_high':['warning_high','wh','warn_high'],
'control_low':['control_low','cl','control_lsl'], 'control_high':['control_high','ch','control_usl'],
'spec_low':['spec_low','lsl','lower_spec'], 'spec_high':['spec_high','usl','upper_spec'], 'target':['target','nominal','setpoint'],
'reaction_plan':['reaction_plan','reaction','action_if_fail'], 'sop_page':['sop_page','page'], 'sop_section':['sop_section','section']}


def auto_mapping(columns: list[Any]) -> dict[str,str]:
    normalized={_norm(c):str(c) for c in columns}; out={}
    for field,names in ALIASES.items():
        for n in names:
            if n in normalized: out[field]=normalized[n]; break
    return out


def _dt(v):
    if v is None or (isinstance(v,float) and math.isnan(v)) or pd.isna(v): return None
    x=pd.to_datetime(v,errors='coerce')
    return None if pd.isna(x) else x.to_pydatetime()


def _text(v):
    if v is None or pd.isna(v): return ''
    return str(v).strip()


def _num(v):
    if v is None or pd.isna(v) or str(v).strip()=='': return None
    try:return float(v)
    except:return None


def normalize_pm_status(v: str) -> str:
    s=_norm(v)
    return {'open':'Pending','pending':'Pending','plan':'Scheduled','planned':'Scheduled','scheduled':'Scheduled','wip':'In Progress','in_progress':'In Progress','delay':'Overdue','late':'Overdue','overdue':'Overdue','defer':'Deferred','deferred':'Deferred','done':'Completed','complete':'Completed','completed':'Completed','cancel':'Cancelled','cancelled':'Cancelled'}.get(s,v.strip().title() or 'Pending')


def dataframe_to_pm_backlog(df: pd.DataFrame,mapping:dict[str,str]):
    rows=[]; errors=[]
    for idx,r in df.iterrows():
        eq=_text(r.get(mapping.get('equipment_id',''))); pm=_text(r.get(mapping.get('pm_id',''))); name=_text(r.get(mapping.get('pm_name','')))
        if not eq or not (pm or name): errors.append(f'Row {idx+2}: equipment and PM identifier/name required'); continue
        if not pm: pm=re.sub(r'\W+','_',name.upper()).strip('_')[:100]
        due=_dt(r.get(mapping.get('original_due_date','')))
        data={'equipment_id':eq,'pm_id':pm,'pm_name':name or pm,'original_due_date':due,'scheduled_date':_dt(r.get(mapping.get('scheduled_date',''))),'last_completion_date':_dt(r.get(mapping.get('last_completion_date',''))),'status':normalize_pm_status(_text(r.get(mapping.get('status','Pending')))),'assigned_to':_text(r.get(mapping.get('assigned_to',''))),'estimated_hours':_num(r.get(mapping.get('estimated_hours',''))) or 0.0,'priority':_text(r.get(mapping.get('priority','Normal'))) or 'Normal','deferral_reason':_text(r.get(mapping.get('deferral_reason',''))),'sop_path':_text(r.get(mapping.get('sop_path',''))),'report_path':_text(r.get(mapping.get('report_path','')))}
        rows.append(data)
    return rows,errors


NUM=r'[-+]?\d+(?:\.\d+)?'
def parse_spec(text: Any) -> dict[str,Any]:
    raw=_text(text); s=raw.lower().replace('−','-').replace('–','-').replace('~','-').replace('＋','+')
    if not raw:return {'input_type':'Text','acceptance_text':''}
    if any(k in s for k in ['pass','ok','no damage','no leak','visual']): return {'input_type':'Pass / Fail','acceptance_text':raw}
    m=re.search(rf'({NUM})\s*(?:±|\+/-)\s*({NUM})',s)
    if m:
        t=float(m.group(1)); tol=abs(float(m.group(2))); return {'input_type':'Numeric','target':t,'spec_low':t-tol,'spec_high':t+tol}
    m=re.search(rf'^\s*({NUM})\s*(?:-|to)\s*({NUM})\s*$',s)
    if m:return {'input_type':'Numeric','spec_low':float(m.group(1)),'spec_high':float(m.group(2))}
    m=re.search(rf'(?:<=|≤|max(?:imum)?)\s*({NUM})|({NUM})\s*max',s)
    if m:return {'input_type':'Numeric','spec_high':float(m.group(1) or m.group(2))}
    m=re.search(rf'(?:>=|≥|min(?:imum)?)\s*({NUM})|({NUM})\s*min',s)
    if m:return {'input_type':'Numeric','spec_low':float(m.group(1) or m.group(2))}
    m=re.fullmatch(rf'\s*({NUM})\s*',s)
    if m:return {'input_type':'Numeric','target':float(m.group(1))}
    return {'input_type':'Text','acceptance_text':raw,'ambiguous':True}


def dataframe_to_pm_specs(df:pd.DataFrame,mapping:dict[str,str],default_pm_id:str=''):
    rows=[]; warnings=[]
    for idx,r in df.iterrows():
        pm=_text(r.get(mapping.get('pm_id',''))) or default_pm_id; activity=_text(r.get(mapping.get('activity','')))
        if not pm or not activity: warnings.append(f'Row {idx+2}: PM ID and activity required'); continue
        step_raw=r.get(mapping.get('step_no','')); step=int(_num(step_raw) or len(rows)+1)
        parsed=parse_spec(r.get(mapping.get('spec','')))
        row={'pm_id':pm,'step_no':step,'activity':activity,'method':_text(r.get(mapping.get('method',''))),'unit':_text(r.get(mapping.get('unit',''))),'reaction_plan':_text(r.get(mapping.get('reaction_plan',''))),'sop_path':_text(r.get(mapping.get('sop_path',''))),'sop_page':_text(r.get(mapping.get('sop_page',''))),'sop_section':_text(r.get(mapping.get('sop_section','')))}
        row.update({k:v for k,v in parsed.items() if k!='ambiguous'})
        for f in ['target','warning_low','warning_high','control_low','control_high','spec_low','spec_high']:
            if f in mapping and _num(r.get(mapping[f])) is not None: row[f]=_num(r.get(mapping[f])); row['input_type']='Numeric'
        if parsed.get('ambiguous'): warnings.append(f'Row {idx+2}: specification kept as text: {parsed.get("acceptance_text","")}')
        if row.get('spec_low') is not None and row.get('spec_high') is not None and row['spec_low']>row['spec_high']:
            warnings.append(f'Row {idx+2}: lower limit exceeds upper limit'); continue
        rows.append(row)
    return rows,warnings


def evaluate_measurement(spec:Any,value_text:str,value_numeric:float|None) -> str:
    if getattr(spec,'input_type','Text')=='Numeric':
        if value_numeric is None:return 'INVALID'
        v=value_numeric
        if spec.spec_low is not None and v<spec.spec_low or spec.spec_high is not None and v>spec.spec_high:return 'SPECIFICATION FAILURE'
        if spec.control_low is not None and v<spec.control_low or spec.control_high is not None and v>spec.control_high:return 'CONTROL FAILURE'
        if spec.warning_low is not None and v<spec.warning_low or spec.warning_high is not None and v>spec.warning_high:return 'WARNING'
        return 'PASS'
    if getattr(spec,'input_type','')=='Pass / Fail':
        return 'PASS' if _norm(value_text) in {'pass','ok','yes','good','acceptable'} else 'FAIL'
    return 'RECORDED' if _text(value_text) else 'INVALID'


def calculate_next_due(schedule_type:str,frequency_value:float|None,frequency_unit:str,anchor_mode:str,original_due:datetime|None,last_completion:datetime|None,now:datetime|None=None) -> datetime|None:
    now=now or datetime.now(); base=original_due if anchor_mode=='Original Due' else last_completion
    if schedule_type in {'One Time','Event Triggered'}: return original_due
    if not base:return original_due
    n=frequency_value or 0
    units=frequency_unit.lower()
    if units.startswith('day'): delta=timedelta(days=n)
    elif units.startswith('week'): delta=timedelta(weeks=n)
    elif units.startswith('hour'): delta=timedelta(hours=n)
    elif units.startswith('month'):
        months=max(1,int(n)); y=base.year+(base.month-1+months)//12; m=(base.month-1+months)%12+1
        import calendar; d=min(base.day,calendar.monthrange(y,m)[1]); return base.replace(year=y,month=m,day=d)
    elif units.startswith('year'):
        try:return base.replace(year=base.year+max(1,int(n)))
        except ValueError:return base.replace(month=2,day=28,year=base.year+max(1,int(n)))
    else:return None
    return base+delta


def pm_window(due:datetime,early_days:int=0,grace_days:int=0):
    return due-timedelta(days=max(0,early_days)), due+timedelta(days=max(0,grace_days))


def workload_by_day(tasks:list[Any]):
    out={}
    for t in tasks:
        d=t.scheduled_date or t.original_due_date
        if not d:continue
        key=d.date().isoformat(); out[key]=out.get(key,0.0)+float(t.estimated_hours or 0)
    return out


def readonly_open_copy(path:str) -> str:
    src=Path(path)
    if not src.exists(): raise FileNotFoundError(path)
    root=Path(tempfile.gettempdir())/'EquipmentManagerReadOnly'; root.mkdir(parents=True,exist_ok=True)
    dst=root/f'{datetime.now():%Y%m%d_%H%M%S_%f}_{src.name}'; shutil.copy2(src,dst)
    try: os.chmod(dst,0o444)
    except OSError: pass
    if os.name=='nt': os.startfile(str(dst))
    elif shutil.which('xdg-open'): subprocess.Popen(['xdg-open',str(dst)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return str(dst)


def copy_clipboard_image(image, root:str, entity_type:str, entity_key:str) -> str:
    folder=Path(root)/'Attachments'/entity_type/entity_key; folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'{datetime.now():%Y%m%d_%H%M%S_%f}_clipboard.png'
    if not image.save(str(path),'PNG'): raise IOError('Could not save clipboard image')
    return str(path)
