from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_user_data(tg_id, date_str):
    # Try to get existing record for the specific date
    res = supabase.table("user_configs").select("*").eq("telegram_id", str(tg_id)).eq("log_date", date_str).execute()
    data = res.data[0] if res.data else {}
    
    # Independently propagate gemini_key if missing today
    if not data.get('gemini_key'):
        recent_key = (supabase.table("user_configs")
                      .select("gemini_key")
                      .eq("telegram_id", str(tg_id))
                      .not_.is_("gemini_key", "null")
                      .order("log_date", desc=True)
                      .limit(1)
                      .execute())
        if recent_key.data:
            data['gemini_key'] = recent_key.data[0]['gemini_key']

    # Independently propagate garmin_session if missing today
    if not data.get('garmin_session'):
        recent_gs = (supabase.table("user_configs")
                     .select("garmin_session")
                     .eq("telegram_id", str(tg_id))
                     .not_.is_("garmin_session", "null")
                     .order("log_date", desc=True)
                     .limit(1)
                     .execute())
        if recent_gs.data:
            data['garmin_session'] = recent_gs.data[0]['garmin_session']
            
    # Independently propagate last_notified if missing today
    if not data.get('last_notified'):
        recent_ln = (supabase.table("user_configs")
                     .select("last_notified")
                     .eq("telegram_id", str(tg_id))
                     .not_.is_("last_notified", "null")
                     .order("log_date", desc=True)
                     .limit(1)
                     .execute())
        if recent_ln.data:
            data['last_notified'] = recent_ln.data[0]['last_notified']
        else:
            data['last_notified'] = {}
            
    # Ensure standard fields exist if it's a new dict
    if 'calories_consumed' not in data: data['calories_consumed'] = 0
    if 'weight' not in data: data['weight'] = None
    
    return data

def sync_to_supabase(tg_id, date_str, updates):
    data = {"telegram_id": str(tg_id), "log_date": date_str, **updates}
    supabase.table("user_configs").upsert(data, on_conflict="telegram_id, log_date").execute()
