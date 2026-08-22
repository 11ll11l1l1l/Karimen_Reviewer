from __future__ import annotations
import ast, json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def top_functions(path: Path) -> list[str]:
    tree=ast.parse(path.read_text(encoding='utf-8'))
    return [n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]

def duplicates(items):
    return sorted({x for x in items if items.count(x)>1})

errors=[]
app_funcs=top_functions(ROOT/'app.py')
core_funcs=top_functions(ROOT/'karimen_core.py')
if duplicates(app_funcs): errors.append(f'duplicate app functions: {duplicates(app_funcs)}')
if duplicates(core_funcs): errors.append(f'duplicate core functions: {duplicates(core_funcs)}')

manifest=json.loads((ROOT/'compatibility_manifest_v43.json').read_text(encoding='utf-8'))
missing_app=sorted(set(manifest['app_functions'])-set(app_funcs))
missing_core=sorted(set(manifest['core_functions'])-set(core_funcs))
if missing_app: errors.append(f'v4.3 app functions removed: {missing_app}')
if missing_core: errors.append(f'v4.3 core functions removed: {missing_core}')

app_text=(ROOT/'app.py').read_text(encoding='utf-8')
required_markers=[
    'BUILD = "4.4 Polished"',
    'Natural neural voice (online)',
    'Saved Rules', 'Image Drill', 'Guess Check',
    'Supabase ranking connected and write-tested',
    'A1 only', 'B1 only',
]
for marker in required_markers:
    if marker not in app_text: errors.append(f'missing release marker: {marker}')

# Mascot assets required by existing category/reaction behavior.
required_assets=[
    'category_exam.png','category_legal.png','category_night.png','category_parking.png',
    'category_pedestrian.png','category_railroad.png','category_signals.png','category_speed.png',
    'reaction_comeback.png','reaction_correct.png','reaction_double_wrong.png','reaction_idle.png',
    'reaction_pleading.png','reaction_streak.png','reaction_victory.png','reaction_wrong.png',
]
for name in required_assets:
    if not (ROOT/'assets'/'mascots'/name).exists(): errors.append(f'missing mascot asset: {name}')

# Never ship obvious live secret values in source/config examples.
for path in [ROOT/'app.py', ROOT/'STREAMLIT_SECRETS_EXAMPLE.toml', ROOT/'README.md']:
    text=path.read_text(encoding='utf-8',errors='ignore')
    if re.search(r'sbp_[A-Za-z0-9_-]{20,}', text): errors.append(f'possible Supabase secret committed in {path.name}')

if errors:
    print('RELEASE_AUDIT_FAILED')
    for e in errors: print('-',e)
    raise SystemExit(1)
print('RELEASE_AUDIT_OK')
print('v4.3 app functions preserved:',len(manifest['app_functions']))
print('v4.3 core functions preserved:',len(manifest['core_functions']))
print('current app functions:',len(app_funcs))
print('current core functions:',len(core_funcs))
