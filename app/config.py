import os
import pytz

# --- Constants ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
IST = pytz.timezone('Asia/Kolkata')
MODEL_ID = "gemini-2.0-flash"
PORT = int(os.environ.get('PORT', 8080))
MASTER_KEY = os.environ.get('MASTER_KEY') # For encryption/decryption
