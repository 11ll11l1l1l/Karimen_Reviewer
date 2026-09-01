from pathlib import Path
import json, sys, collections, statistics, zipfile, lzma, base64, io
ROOT=Path(__file__).resolve().parent
DATA_XZ=ROOT/'data/questions_v53.json.xz'
def joined_parts(directory, pattern):
    parts=sorted(directory.glob(pattern)) if directory.exists() else []
    if not parts: return None
    return base64.b64decode(''.join(p.read_text(encoding='ascii').strip() for p in parts))
packed=DATA_XZ.read_bytes() if DATA_XZ.exists() else joined_parts(ROOT/'data/deploy','questions_v53_xz_part*.b64')
DOC=json.loads(lzma.decompress(packed).decode('utf8') if packed else (ROOT/'data/questions.json').read_text(encoding='utf8'))
BUNDLE=ROOT/'assets'/'honmen_questions.zip'
bundle_bytes=BUNDLE.read_bytes() if BUNDLE.exists() else joined_parts(ROOT/'assets/deploy','honmen_zip_part*.b64')
try:
    BUNDLED=set(zipfile.ZipFile(io.BytesIO(bundle_bytes),'r').namelist()) if bundle_bytes else set()
except Exception:
    BUNDLED=set()
qs=DOC['questions']; meta=DOC['metadata']; errors=[]
if len(qs)!=1550: errors.append(f'Expected 1550 questions, found {len(qs)}')
ids=[q.get('id') for q in qs]
if len(ids)!=len(set(ids)): errors.append('Duplicate question IDs found')
counts=collections.Counter(q.get('bank') for q in qs)
if counts != {'Karimen':650,'Honmen':900}: errors.append(f'Unexpected bank counts: {counts}')
for s in range(1,11):
    n=sum(q.get('bank')=='Honmen' and int(q.get('set') or 0)==s for q in qs)
    if n!=90: errors.append(f'Honmen set {s} has {n}, expected 90')
image_refs=[]
required_detail=['rule_title','rule_summary','why_answer','practical_meaning','exam_trap','official_section','explanation_quality','explanation_detailed']
for q in qs:
    for field in ['id','bank','category','explanation','content_key']+required_detail:
        if not q.get(field): errors.append(f"{q.get('id')}: missing {field}")
    if not str(q.get('question_en') or '').strip(): errors.append(f"{q.get('id')}: missing English question")
    if not str(q.get('question_en_exam') or '').strip(): errors.append(f"{q.get('id')}: missing Exam English question")
    if not isinstance(q.get('answer'),bool): errors.append(f"{q.get('id')}: answer not bool")
    if len(q.get('explanation_detailed','')) < 500: errors.append(f"{q.get('id')}: detailed explanation is too short")
    if q.get('explanation_quality','').endswith('review_recommended'):
        errors.append(f"{q.get('id')}: still has only category-level explanation")
    if not any(isinstance(src,dict) and src.get('key')=='NPA_KYOUSOKU_2024_11' for src in q.get('sources') or []):
        errors.append(f"{q.get('id')}: missing NPA guide source anchor")
    for img in q.get('images') or []:
        image_refs.append(img)
        if not (ROOT/img).exists() and img not in BUNDLED: errors.append(f'Missing image: {img}')
if len(image_refs)!=228: errors.append(f'Expected 228 image refs, found {len(image_refs)}')
if sum(q.get('verification_status')=='officially_verified_fallback' for q in qs)!=4:
    errors.append('Expected 4 pre-existing officially verified Honmen fallback answers')
corrections=[q for q in qs if q.get('answer_corrected_from_source')]
if len(corrections)!=41: errors.append(f'Expected 41 audited source-key corrections, found {len(corrections)}')
for q in corrections:
    if not isinstance(q.get('source_answer'),bool): errors.append(f"{q['id']}: corrected answer missing source_answer")
    if not q.get('answer_correction_reason'): errors.append(f"{q['id']}: corrected answer missing correction reason")
if int(meta.get('answer_key_correction_count_v51') or 0)!=41:
    errors.append('Metadata correction count is not 41')
quality=collections.Counter(q.get('explanation_quality') for q in qs)
if quality.get('official_category_anchor_review_recommended',0)!=0:
    errors.append(f'Category-only explanations remain: {quality.get("official_category_anchor_review_recommended",0)}')
if meta.get('version')!='5.3-english-first-exam-translation': errors.append(f"Unexpected metadata version: {meta.get('version')}")
english_count=sum(bool(str(q.get('question_en') or '').strip()) for q in qs)
exam_english_count=sum(bool(str(q.get('question_en_exam') or '').strip()) for q in qs)
honmen_english_count=sum(q.get('bank')=='Honmen' and bool(str(q.get('question_en_exam') or '').strip()) for q in qs)
if english_count!=1550: errors.append(f'Expected English for 1550 questions, found {english_count}')
if exam_english_count!=1550: errors.append(f'Expected Exam English for 1550 questions, found {exam_english_count}')
if honmen_english_count!=900: errors.append(f'Expected English for all 900 Honmen questions, found {honmen_english_count}')
if int(meta.get('english_question_count') or 0)!=1550: errors.append('Metadata English question count is not 1550')
if int(meta.get('honmen_english_translation_count') or 0)!=900: errors.append('Metadata Honmen English translation count is not 900')
import re
japanese_chars=re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')
for q in qs:
    if japanese_chars.search(str(q.get('question_en_exam') or '')):
        errors.append(f"{q['id']}: Japanese characters remain in Exam English")
    if q.get('bank')=='Honmen' and q.get('translation_status')!='exam_english_v53_human_reviewed':
        errors.append(f"{q['id']}: Honmen translation status not v5.3 reviewed")
# Ensure the imminent 2026-09-01 statutory-speed change is represented explicitly.
for qid in ['KARIMEN-S07-Q004','KARIMEN-S09-Q014']:
    q=next((x for x in qs if x['id']==qid),None)
    if not q or not q.get('answer_schedule') or q['answer_schedule'][0].get('from')!='2026-09-01':
        errors.append(f'{qid}: missing 2026-09-01 answer schedule')

# v5.1 explanation-quality regression guards.
for q in qs:
    if 'Apply the rule above to the exact wording' in q.get('why_answer',''):
        errors.append(f"{q['id']}: generic WHY placeholder remains")
    if q.get('exam_trap','').startswith('The statement matches the applicable rule') or q.get('exam_trap','').startswith('The statement contains a condition'):
        errors.append(f"{q['id']}: generic exam-trap placeholder remains")
    if q.get('practical_meaning','').startswith('The point of this rule is to keep the driver'):
        errors.append(f"{q['id']}: generic practical-meaning placeholder remains")

legacy=json.loads((ROOT/'data/legacy_id_map.json').read_text())
if len(legacy)!=650: errors.append(f'Legacy map count {len(legacy)} != 650')
lengths=[len(q.get('explanation_detailed','')) for q in qs]
print('Questions:',len(qs))
print('English questions:',english_count,'Exam English:',exam_english_count,'Honmen English:',honmen_english_count)
print('Banks:',dict(counts))
print('Image refs:',len(image_refs))
print('Distinct content:',len({q['content_key'] for q in qs}))
print('Detailed explanation chars: min',min(lengths),'median',int(statistics.median(lengths)),'mean',round(statistics.mean(lengths),1))
print('Explanation quality:',dict(quality))
print('Audited source-key corrections:',len(corrections))
print('Errors:',len(errors))
for e in errors: print('-',e)
sys.exit(1 if errors else 0)
