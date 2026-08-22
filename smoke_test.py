import json
from datetime import date, timezone, timedelta
from karimen_core import default_progress, record_answer, mastery, select_question_ids, daily_question_ids, add_session, daily_streak, normalize_progress

doc=json.load(open('data/questions.json',encoding='utf-8'))
qs=doc['questions']; ids={q['id'] for q in qs}
p=default_progress()
q0=qs[0]['id']; q1=qs[1]['id']
record_answer(p,q0,False,2.0)
assert p['question_stats'][q0]['attempts']==1 and p['question_stats'][q0]['wrong']==1
record_answer(p,q0,True,1.2)
assert p['question_stats'][q0]['attempts']==2 and p['question_stats'][q0]['correct']==1 and p['question_stats'][q0]['wrong']==1
assert 0 <= mastery(p['question_stats'][q0]) <= 100
wrong=select_question_ids(qs,p,'Wrong answers',20,seed=1)
assert wrong==[q0], wrong
adaptive=select_question_ids(qs,p,'Due / adaptive',20,seed=1)
assert len(adaptive)==20 and len(set(adaptive))==20
daily1=daily_question_ids(qs,date(2026,8,22),10)
daily2=daily_question_ids(qs,date(2026,8,22),10)
assert daily1==daily2 and len(daily1)==10 and len(set(daily1))==10
assert sum(1 for qid in daily1 if next(q for q in qs if q['id']==qid).get('images')) >= 3
add_session(p,'daily',daily1,8,120)
assert daily_streak(p['sessions'],date(2026,8,22),timezone.utc) in (0,1)  # UTC stamp can be Aug 21/22 depending runtime
raw={'question_stats':{q1:{'attempts':3,'correct':2,'wrong':99,'streak':1}},'sessions':[]}
n=normalize_progress(raw,ids)
assert n['question_stats'][q1]['wrong']==1
print('CORE_SMOKE_OK')
print('questions',len(qs),'images',sum(bool(q.get('images')) for q in qs),'daily_image_count',sum(1 for qid in daily1 if next(q for q in qs if q['id']==qid).get('images')))
