-- ============================================================
-- Supabase 数据库初始化 SQL
-- ============================================================
-- 使用方法：
-- 1. 登录 Supabase → 选你的项目
-- 2. 左侧菜单点 "SQL Editor"
-- 3. 点 "New query"
-- 4. 把这个文件全部内容复制进去
-- 5. 点 "Run"（或 Ctrl+Enter）
-- 6. 看到 "Success. No rows returned" 就成功了
-- ============================================================

-- 对话表
CREATE TABLE IF NOT EXISTS conversations (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '新对话',
    model_id TEXT,
    system_prompt TEXT,
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL
);

-- 消息表
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL
        REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    meta JSONB DEFAULT '{}'::jsonb,
    created_at DOUBLE PRECISION NOT NULL
);

-- 索引（加快查询）
CREATE INDEX IF NOT EXISTS idx_messages_conv
    ON messages(conversation_id);

CREATE INDEX IF NOT EXISTS idx_conv_updated
    ON conversations(updated_at DESC);

-- ============================================================
-- 注意：这个项目用的是 service_role key（后端密钥），
-- 默认绕过 RLS（Row Level Security），所以不需要配置 RLS 策略。
-- 如果以后要做多用户，再加 RLS 即可。
-- ============================================================
