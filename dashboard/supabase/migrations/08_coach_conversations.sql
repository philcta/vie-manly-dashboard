CREATE TABLE IF NOT EXISTS coach_conversations (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id text NOT NULL,
    role text NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content text NOT NULL,
    context_snapshot jsonb,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_coach_conv_session ON coach_conversations (session_id, created_at);

ALTER TABLE coach_conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_coach" ON coach_conversations FOR SELECT TO anon USING (true);
