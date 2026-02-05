from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_user_data(tg_id, date_str):
    # Try to get existing record for the specific date
    res = supabase.table("user_configs").select("*").eq("telegram_id", str(tg_id)).eq("log_date", date_str).execute()
    data = res.data[0] if res.data else None
    
    # If key is found in the current record, we're good
    if data and data.get('gemini_key'):
        return data
    
    # If key or garmin_session is missing, fetch the most recent valid record
    recent = (supabase.table("user_configs")
              .select("gemini_key, garmin_session")
              .eq("telegram_id", str(tg_id))
              .not_.is_("gemini_key", "null")
              .order("log_date", desc=True)
              .limit(1)
              .execute())
    
    if recent.data:
        res_data = recent.data[0]
        key = res_data.get('gemini_key')
        gs = res_data.get('garmin_session')
        
        if data:
            data['gemini_key'] = key
            data['garmin_session'] = gs
            return data
        # If no record existed for today, return a template
        return {"gemini_key": key, "garmin_session": gs, "calories_consumed": 0, "weight": None}
    
    return data

def sync_to_supabase(tg_id, date_str, updates):
    data = {"telegram_id": str(tg_id), "log_date": date_str, **updates}
    supabase.table("user_configs").upsert(data, on_conflict="telegram_id, log_date").execute()
