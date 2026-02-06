import os
import sys
# Add parent dir to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import supabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    logger.info("Starting data migration from user_configs to new schema...")
    
    # 1. Fetch all legacy data
    res = supabase.table("user_configs").select("*").execute()
    legacy_rows = res.data
    logger.info(f"Found {len(legacy_rows)} legacy records.")

    for row in legacy_rows:
        tg_id = str(row['telegram_id'])
        date = row['log_date']
        
        # 2. Update/Insert User
        user_row = {
            "telegram_id": tg_id,
            "gemini_key": row.get('gemini_key')
        }
        supabase.table("users").upsert(user_row, on_conflict="telegram_id").execute()

        # 3. Update/Insert Integration (if garmin_session exists)
        if row.get('garmin_session'):
            integration_row = {
                "user_id": tg_id,
                "provider": "garmin",
                "session_data": row['garmin_session'],
                "is_active": True
            }
            supabase.table("user_integrations").upsert(integration_row, on_conflict="user_id, provider").execute()

        # 4. Update/Insert Daily Metrics
        metrics_row = {
            "user_id": tg_id,
            "log_date": date,
            "weight": row.get('weight'),
            "calories_consumed": row.get('calories_consumed', 0),
            "last_notified": row.get('last_notified', {})
        }
        # Note: Advanced metrics will be re-fetched by the bot periodically, 
        # but we migrate core ones here.
        supabase.table("daily_metrics").upsert(metrics_row, on_conflict="user_id, log_date").execute()

    logger.info("Migration complete!")

if __name__ == "__main__":
    migrate()
