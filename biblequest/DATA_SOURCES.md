# BibleQuest content-source strategy

BibleQuest should prefer public-domain or openly licensed structured resources and retain provenance on every imported record.

## Primary planned sources

- Berean Standard Bible (BSB) — public domain Bible text. Download/import rather than scraping.
- World English Bible (WEB) — public domain Bible text and safe fallback translation.
- unfoldingWord Translation Questions — CC BY-SA 4.0. Structured chapter/verse questions and answers.
- unfoldingWord Open Bible Stories — open-licensed narrative material for Story Adventure.
- unfoldingWord Translation/Study Notes — open-licensed contextual material; use with provenance and classification.
- STEPBible Data — CC BY 4.0 datasets for people, places, names, lexical/original-language metadata.
- OpenBible.info cross references — open cross-reference dataset for connection games.

## Rules

1. Preserve `source_name`, `source_version`, `source_url`, `license`, and `attribution` for imported records.
2. Distinguish content classes: `fact`, `context`, `interpretation`, `wisdom`, `open_question`.
3. AI may transform verified source material into game formats, but it must not silently invent the underlying biblical fact.
4. ShareAlike material should remain traceable and separable from BibleQuest-original data/code.
5. Bible translations with restrictive redistribution terms should not be bundled unless permission/licensing is confirmed.

The current alpha includes a small normalized starter set so the app is playable before bulk ingestion.
