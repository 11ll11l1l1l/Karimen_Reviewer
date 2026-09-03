-- ALAM migration 013: enforce valid parent references for panel-comment replies.
-- GitHub JSON remains the audit source of truth; this constraint protects the
-- Supabase query mirror from accepting dangling reply_to values during sync.

CREATE INDEX IF NOT EXISTS idx_agent_comments_reply_to
    ON public.agent_comments (reply_to)
    WHERE reply_to IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.agent_comments'::regclass
          AND conname = 'agent_comments_reply_to_fkey'
    ) THEN
        ALTER TABLE public.agent_comments
            ADD CONSTRAINT agent_comments_reply_to_fkey
            FOREIGN KEY (reply_to)
            REFERENCES public.agent_comments (id)
            ON DELETE SET NULL
            NOT VALID;
    END IF;
END
$$;

ALTER TABLE public.agent_comments
    VALIDATE CONSTRAINT agent_comments_reply_to_fkey;
