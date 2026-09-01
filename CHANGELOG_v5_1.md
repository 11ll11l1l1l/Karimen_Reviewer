# Japan Driving License Exam Reviewer v5.1

## Main change

v5.1 upgrades the bank from short/source-result feedback to structured teaching explanations for all 1,550 questions.

Each question now provides:

- Why the answer is true/false
- Rule to remember
- Practical driving meaning
- Common exam trap
- Official guide section
- Source/verification links

The explanation audit removes the former generic WHY/TRAP/PRACTICAL placeholders. Numeric, timing, permission/exception, and image-dependent questions call out the exact tested feature.

## Bank integrity

- 1,550 total source records
- Karimen: 650
- Honmen: 900
- 228 image references
- 1,539 distinct-content groups
- Exact source duplicates retained for provenance but de-duplicated in normal selection
- 41 high-confidence Honmen source-key corrections retained with original `source_answer` and an audit reason
- Effective-date handling for the 2026-09-01 statutory-speed amendment

## Official sources

- National Police Agency: 交通の方法に関する教則 — https://www.npa.go.jp/bureau/traffic/20241113kyousoku.pdf
- National Police Agency: 生活道路における法定速度の引下げ — https://www.npa.go.jp/bureau/traffic/seikatsudouro/seikatsudoro.html
- Osaka Prefectural Police ordinary/provisional licence exam information — https://www.police.pref.osaka.lg.jp/tetsuduki/untenmenkyo/juken/choku/3709.html

## Regression result

- Python compile: PASS
- Question/data validation: PASS
- Core smoke test: PASS
- Runtime stub test: PASS
- Strict Streamlit-state/game-state regression: PASS
- Supabase integration/permission stubs: PASS
- v4.3 compatibility release audit: PASS
- v4.3 app functions preserved: 92/92
- v4.3 core functions preserved: 16/16
- Current app functions: 116
- Current core functions: 24

The local execution environment does not include real Streamlit, Supabase, or edge-tts packages. The included GitHub Actions workflow installs the real dependencies and runs Streamlit AppTest plus a headless server health check after push.
