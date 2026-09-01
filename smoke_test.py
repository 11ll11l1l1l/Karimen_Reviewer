import json, lzma, base64
from pathlib import Path
from datetime import date
from karimen_core import default_progress, record_answer, mastery, select_question_ids, daily_question_ids, normalize_progress

ROOT=Path(__file__).resolve().parent
packed=(ROOT/'data/questions_v53.json.xz').read_bytes() if (ROOT/'data/questions_v53.json.xz').exists() else None
if packed is None:
    parts=sorted((ROOT/'data/deploy').glob('questions_v53_xz_part*.b64'))
    packed=base64.b64decode(''.join(x.read_text(encoding='ascii').strip() for x in parts)) if parts else None
doc=json.loads(lzma.decompress(packed).decode('utf8')) if packed else json.load(open(ROOT/'data/questions.json',encoding='utf8')); qs=doc['questions']; ids={q['id'] for q in qs}
assert len(qs)==1550
assert all(str(q.get('question_en') or '').strip() for q in qs)
assert all(str(q.get('question_en_exam') or '').strip() for q in qs)
assert sum(q['bank']=='Honmen' and bool(str(q.get('question_en_exam') or '').strip()) for q in qs)==900
p=default_progress()
# Hard unseen priority: after heavily practicing one record, it cannot crowd out unseen records.
seen=qs[0]
for _ in range(8): record_answer(p,seen['id'],False,1.0)
chosen=select_question_ids(qs,p,'Coverage first',50,seed=7)
assert len(chosen)==50 and len(set(chosen))==50 and seen['id'] not in chosen
assert all(p['question_stats'].get(qid,{}).get('attempts',0)==0 for qid in chosen)
# Mark every question in a small pool once except one, then the one unseen item must lead the next queue.
small=qs[:8]; p2=default_progress()
for q in small[:-1]: record_answer(p2,q['id'],True,1.0)
lead=select_question_ids(small,p2,'Coverage first',3,seed=3)
assert small[-1]['id'] in lead
# Legacy v4 A1/B1 ids migrate into Karimen IDs.
raw={'question_stats':{'A1-S14-Q001':{'attempts':2,'correct':1},'B1-S01-Q001':{'attempts':3,'correct':2}},'bookmarks':['A1-S14-Q001'],'sessions':[{'bank':'B1','question_ids':['B1-S01-Q001']} ]}
n=normalize_progress(raw,ids)
assert 'KARIMEN-S14-Q001' in n['question_stats'] and 'KARIMEN-S01-Q001' in n['question_stats']
assert n['bookmarks']==['KARIMEN-S14-Q001'] and n['sessions'][0]['bank']=='Karimen'
# Daily remains deterministic for same profile/date/progress snapshot.
d1=daily_question_ids(qs,date(2026,8,29),10,progress=default_progress(),player_token='Geesene')
d2=daily_question_ids(qs,date(2026,8,29),10,progress=default_progress(),player_token='Geesene')
assert d1==d2 and len(d1)==10 and len(set(d1))==10
print('CORE_SMOKE_OK')
print('questions',len(qs),'karimen',sum(q['bank']=='Karimen' for q in qs),'honmen',sum(q['bank']=='Honmen' for q in qs))
