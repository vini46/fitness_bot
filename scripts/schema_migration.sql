-- 1. Create Users Table
CREATE TABLE IF NOT EXISTS users (
    telegram_id TEXT PRIMARY KEY,
    gemini_key TEXT,
    timezone TEXT DEFAULT 'Asia/Kolkata',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Create User Integrations Table (Garmin, etc.)
CREATE TABLE IF NOT EXISTS user_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT REFERENCES users(telegram_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    session_data JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, provider)
);

-- 3. Create Daily Metrics Table
CREATE TABLE IF NOT EXISTS daily_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT REFERENCES users(telegram_id) ON DELETE CASCADE,
    log_date DATE NOT NULL,
    weight DECIMAL,
    calories_consumed INT DEFAULT 0,
    steps INT DEFAULT 0,
    sleep_score INT,
    body_battery INT,
    stress_level INT,
    last_notified JSONB DEFAULT '{}'::jsonb,
    UNIQUE(user_id, log_date)
);

-- Index for faster daily queries
CREATE INDEX IF NOT EXISTS idx_metrics_user_date ON daily_metrics(user_id, log_date);
