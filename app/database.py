from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_KEY
import logging

logger = logging.getLogger(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_user_data(tg_id, date_str):
    """Fetch user settings and daily metrics in a single logical view."""
    try:
        # 1. Fetch from 'users'
        user_res = supabase.table("users").select("*").eq("telegram_id", str(tg_id)).execute()
        user_info = user_res.data[0] if user_res.data else {}

        # 2. Fetch from 'daily_metrics'
        metrics_res = (supabase.table("daily_metrics")
                      .select("*")
                      .eq("user_id", str(tg_id))
                      .eq("log_date", date_str)
                      .execute())
        metrics_info = metrics_res.data[0] if metrics_res.data else {}

        # Merge for backward compatibility in the rest of the app
        # This allows the rest of the code to still access things like 'gemini_key' directly
        return {**user_info, **metrics_info}
    except Exception as e:
        logger.error(f"Error fetching data for {tg_id}: {e}")
        return {}

def sync_to_supabase(tg_id, date_str, updates):
    """Update users or daily_metrics as appropriate."""
    try:
        tg_id_str = str(tg_id)
        
        # Split updates into 'users' fields and 'daily_metrics' fields
        user_fields = ["gemini_key", "timezone"]
        metrics_fields = ["weight", "calories_consumed", "steps", "sleep_score", "body_battery", "stress_level", "last_notified"]
        
        u_updates = {k: v for k, v in updates.items() if k in user_fields}
        m_updates = {k: v for k, v in updates.items() if k in metrics_fields}

        if u_updates:
            u_updates["telegram_id"] = tg_id_str
            supabase.table("users").upsert(u_updates, on_conflict="telegram_id").execute()

        if m_updates:
            m_updates["user_id"] = tg_id_str
            m_updates["log_date"] = date_str
            supabase.table("daily_metrics").upsert(m_updates, on_conflict="user_id, log_date").execute()

    except Exception as e:
        logger.error(f"Error syncing to Supabase for {tg_id}: {e}")

def get_weight_history(tg_id):
    """Retrieve weight history from the daily_metrics table."""
    try:
        res = (supabase.table("daily_metrics")
               .select("log_date, weight")
               .eq("user_id", str(tg_id))
               .not_.is_("weight", "null")
               .order("log_date", desc=False)
               .execute())
        return res.data
    except Exception as e:
        logger.error(f"Error fetching weight history for {tg_id}: {e}")
        return []
