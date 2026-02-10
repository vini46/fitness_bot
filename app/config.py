import os
import pytz

# --- Constants ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
IST = pytz.timezone('Asia/Kolkata')
MODEL_ID = "gemini-1.5-flash" # Legacy default
PORT = int(os.environ.get('PORT', 8080))
MASTER_KEY = os.environ.get('MASTER_KEY') # For encryption/decryption

SUPPORTED_PROVIDERS = ["gemini", "openrouter"]
DEFAULT_MODELS = {
    "gemini": "gemini-1.5-flash",
    "openrouter": "google/gemma-2-9b-it:free"
}
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
