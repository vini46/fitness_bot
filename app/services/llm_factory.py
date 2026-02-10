import datetime
import logging
from app.config import DEFAULT_MODELS, SUPPORTED_PROVIDERS, IST
from app.database import get_user_data
from app.services.gemini import get_gemini_response
from app.services.openrouter import get_openrouter_response

logger = logging.getLogger(__name__)

def get_llm_response(tg_id, prompt):
    """
    Generic entry point for LLM responses.
    Determines provider and model based on user settings in the database.
    """
    today = datetime.datetime.now(IST).strftime('%Y-%m-%d')
    user_info = get_user_data(tg_id, today)
    
    if not user_info:
        logger.error(f"Could not fetch user data for {tg_id}")
        return "DATABASE_ERROR"

    # Determine provider
    provider = user_info.get('preferred_provider') or "gemini"
    if provider not in SUPPORTED_PROVIDERS:
        provider = "gemini" # Fallback
        
    # Determine model
    model = user_info.get('preferred_model') or DEFAULT_MODELS.get(provider)
    
    # Get API Key
    key_field = f"{provider}_key"
    api_key = user_info.get(key_field)
    
    if not api_key:
        logger.warning(f"Key missing for provider {provider} for user {tg_id}")
        return "KEY_MISSING"

    # Route to specific service
    try:
        if provider == "gemini":
            return get_gemini_response(api_key, model, prompt)
        elif provider == "openrouter":
            return get_openrouter_response(api_key, model, prompt)
        else:
            return "UNSUPPORTED_PROVIDER"
    except Exception as e:
        logger.error(f"Error in llm_factory for {provider}: {e}")
        return "LLM_SERVICE_ERROR"
