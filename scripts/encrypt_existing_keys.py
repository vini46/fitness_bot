import sys
import os
# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import supabase
from app.utils.crypto import encrypt_value, decrypt_value, _fernet
from cryptography.fernet import Fernet

def migrate_keys():
    if not _fernet:
        print("❌ MASTER_KEY not found in environment!")
        print("Please generate one using: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
        print("Then set it as MASTER_KEY env var and run this script again.")
        return

    print("🔍 Fetching all users...")
    res = supabase.table("users").select("telegram_id, gemini_key").execute()
    
    if not res.data:
        print("✅ No users found.")
        return

    count = 0
    for user in res.data:
        tg_id = user['telegram_id']
        old_key = user.get('gemini_key')
        
        if not old_key:
            continue
            
        # Try decrypting. If it fails, it means it's likely plain text
        try:
            _fernet.decrypt(old_key.encode())
            print(f"⏩ User {tg_id} already has an encrypted key. Skipping.")
        except Exception:
            # Encryption failed, so it's plain text. Let's encrypt it.
            new_key = encrypt_value(old_key)
            supabase.table("users").update({"gemini_key": new_key}).eq("telegram_id", tg_id).execute()
            print(f"🔒 Encrypted key for user {tg_id}")
            count += 1

    print(f"\n✅ Migration complete. {count} keys encrypted.")

if __name__ == "__main__":
    migrate_keys()
