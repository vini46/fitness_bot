-- SQL Script to update users table for Multi-Model Support

-- Add OpenRouter Key column (encrypted via app logic)
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS openrouter_key TEXT;

-- Add Preferred Provider column (defaults to gemini)
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS preferred_provider TEXT DEFAULT 'gemini';

-- Add Preferred Model column
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS preferred_model TEXT;

-- Optional: Add a comment to describe the new columns
COMMENT ON COLUMN public.users.openrouter_key IS 'Encrypted API key for OpenRouter';
COMMENT ON COLUMN public.users.preferred_provider IS 'User selected AI provider (gemini, openrouter)';
COMMENT ON COLUMN public.users.preferred_model IS 'Specific model ID selected by the user';
