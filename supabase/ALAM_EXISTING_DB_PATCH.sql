-- ALAM.ph legacy UUID -> v5 text-ID compatibility bridge
-- Run this BEFORE supabase/ALAM_FULL_SETUP.sql when an earlier ALAM Supabase
-- schema already created public.articles with UUID ids.
--
-- This migration is intentionally non-destructive. It preserves the original
-- UUID tables and their data by renaming them, including their FK relationships.
-- The v5 setup can then create clean text-ID tables under the canonical names.

create extension if not exists pgcrypto;

DO $$
DECLARE
  article_id_type text;
  legacy_mode boolean := false;
BEGIN
  IF to_regclass('public.articles') IS NOT NULL THEN
    SELECT c.data_type
      INTO article_id_type
      FROM information_schema.columns c
     WHERE c.table_schema = 'public'
       AND c.table_name = 'articles'
       AND c.column_name = 'id';

    legacy_mode := article_id_type IS DISTINCT FROM 'text';
  END IF;

  IF legacy_mode THEN
    -- Never overwrite an earlier preserved copy.
    IF to_regclass('public.articles_legacy_20260902') IS NOT NULL THEN
      RAISE EXCEPTION 'Legacy bridge stopped: public.articles_legacy_20260902 already exists while public.articles is still non-text. Inspect the two tables before continuing.';
    END IF;

    -- Rename dependent legacy tables first. PostgreSQL keeps their existing FKs
    -- attached to the renamed legacy articles table automatically.
    IF to_regclass('public.article_sources') IS NOT NULL THEN
      IF to_regclass('public.article_sources_legacy_20260902') IS NOT NULL THEN
        RAISE EXCEPTION 'Legacy bridge stopped: public.article_sources_legacy_20260902 already exists.';
      END IF;
      ALTER TABLE public.article_sources RENAME TO article_sources_legacy_20260902;
    END IF;

    IF to_regclass('public.agent_comments') IS NOT NULL THEN
      IF to_regclass('public.agent_comments_legacy_20260902') IS NOT NULL THEN
        RAISE EXCEPTION 'Legacy bridge stopped: public.agent_comments_legacy_20260902 already exists.';
      END IF;
      ALTER TABLE public.agent_comments RENAME TO agent_comments_legacy_20260902;
    END IF;

    IF to_regclass('public.agent_runs') IS NOT NULL THEN
      IF to_regclass('public.agent_runs_legacy_20260902') IS NOT NULL THEN
        RAISE EXCEPTION 'Legacy bridge stopped: public.agent_runs_legacy_20260902 already exists.';
      END IF;
      ALTER TABLE public.agent_runs RENAME TO agent_runs_legacy_20260902;
    END IF;

    ALTER TABLE public.articles RENAME TO articles_legacy_20260902;

    -- Rename common constraint/index objects left with their old names so the
    -- canonical v5 tables can create their own indexes cleanly.
    IF EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conrelid = 'public.articles_legacy_20260902'::regclass
        AND conname = 'articles_pkey'
    ) THEN
      ALTER TABLE public.articles_legacy_20260902
        RENAME CONSTRAINT articles_pkey TO articles_legacy_20260902_pkey;
    END IF;

    IF to_regclass('public.article_sources_legacy_20260902') IS NOT NULL THEN
      IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.article_sources_legacy_20260902'::regclass
          AND conname = 'article_sources_pkey'
      ) THEN
        ALTER TABLE public.article_sources_legacy_20260902
          RENAME CONSTRAINT article_sources_pkey TO article_sources_legacy_20260902_pkey;
      END IF;
    END IF;

    IF to_regclass('public.agent_comments_legacy_20260902') IS NOT NULL THEN
      IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.agent_comments_legacy_20260902'::regclass
          AND conname = 'agent_comments_pkey'
      ) THEN
        ALTER TABLE public.agent_comments_legacy_20260902
          RENAME CONSTRAINT agent_comments_pkey TO agent_comments_legacy_20260902_pkey;
      END IF;
    END IF;

    IF to_regclass('public.agent_runs_legacy_20260902') IS NOT NULL THEN
      IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.agent_runs_legacy_20260902'::regclass
          AND conname = 'agent_runs_pkey'
      ) THEN
        ALTER TABLE public.agent_runs_legacy_20260902
          RENAME CONSTRAINT agent_runs_pkey TO agent_runs_legacy_20260902_pkey;
      END IF;
    END IF;

    IF to_regclass('public.article_sources_article_idx') IS NOT NULL THEN
      ALTER INDEX public.article_sources_article_idx
        RENAME TO article_sources_legacy_20260902_article_idx;
    END IF;

    -- The failed one-shot setup can already have created this index on the old
    -- articles table before stopping at the missing category column.
    IF to_regclass('public.articles_status_published_idx') IS NOT NULL THEN
      ALTER INDEX public.articles_status_published_idx
        RENAME TO articles_legacy_20260902_status_published_idx;
    END IF;

    RAISE NOTICE 'Legacy UUID ALAM tables preserved with *_legacy_20260902 names. Run ALAM_FULL_SETUP.sql next.';
  ELSE
    RAISE NOTICE 'No legacy UUID public.articles table detected. No rename was required.';
  END IF;
END $$;

-- Verification output. On a migrated project, articles should be absent here
-- until ALAM_FULL_SETUP.sql is run, while articles_legacy_20260902 should exist.
select
  to_regclass('public.articles')::text as current_articles,
  to_regclass('public.articles_legacy_20260902')::text as preserved_legacy_articles;
