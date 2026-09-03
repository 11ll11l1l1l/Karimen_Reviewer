# BibleQuest — Alpha 0.1

A game-first Bible learning PWA designed for mobile use.

## Included now

- Daily 5 and Quick Play
- Context Mode
- Bible Detective
- Story Adventure
- Timeline Challenge
- Bible Journey progress
- Deep/open philosophical question poll
- XP, streak, achievements and local persistence
- PWA/offline cache
- Future `Study Together` placeholder only
- Supabase schema draft with RLS policies
- Open-resource provenance strategy

## Deployment

This folder is static and can be served directly by GitHub Pages. No Python server is required.

For local preview:

```bash
python -m http.server 8080 --directory biblequest
```

Then open `http://localhost:8080`.

## Backend

The alpha intentionally uses `localStorage` until BibleQuest gets a dedicated Supabase project. `supabase/schema.sql` is ready as the starting schema. Do not expose a Supabase secret/service-role key in the browser; only a publishable key belongs in client code, together with RLS.

## Content

See `DATA_SOURCES.md`. The production content strategy is to import public-domain/open datasets instead of manually writing thousands of facts.
