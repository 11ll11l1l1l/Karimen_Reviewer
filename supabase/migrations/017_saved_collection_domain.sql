-- Keep the durable Saved collection domain aligned with the product's bounded
-- collection vocabulary. Browser state already normalizes unknown values, but
-- authenticated writes reach this table through RLS and should fail closed
-- instead of persisting arbitrary labels that other clients cannot interpret.
-- The legacy `saved` value remains accepted for backward compatibility.
DO $$
BEGIN
  IF to_regclass('public.saved_articles') IS NOT NULL
     AND NOT EXISTS (
       SELECT 1
       FROM pg_constraint
       WHERE conrelid = 'public.saved_articles'::regclass
         AND conname = 'saved_articles_collection_domain_check'
     ) THEN
    ALTER TABLE public.saved_articles
      ADD CONSTRAINT saved_articles_collection_domain_check
      CHECK (collection IN ('saved', 'read_later', 'important', 'money', 'japan', 'family', 'ideas'))
      NOT VALID;

    ALTER TABLE public.saved_articles
      VALIDATE CONSTRAINT saved_articles_collection_domain_check;
  END IF;
END
$$;
