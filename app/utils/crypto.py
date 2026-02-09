from cryptography.fernet import Fernet
from app.config import MASTER_KEY
import logging

logger = logging.getLogger(__name__)

# Initialize Fernet only if key is present
_fernet = None
if MASTER_KEY:
    try:
        _fernet = Fernet(MASTER_KEY.encode())
    except Exception as e:
        logger.error(f"Invalid MASTER_KEY format: {e}")

def encrypt_value(value: str) -> str:
    """Encrypt a string value."""
    if not _fernet or not value:
        return value
    return _fernet.encrypt(value.encode()).decode()

def decrypt_value(encrypted_value: str) -> str:
    """Decrypt an encrypted string value."""
    if not _fernet or not encrypted_value:
        return encrypted_value
    try:
        # Check if it looks like a Fernet token (usually starts with gAAAA)
        # If it's not encrypted, decrypt will fail, and we return the original
        return _fernet.decrypt(encrypted_value.encode()).decode()
    except Exception:
        # If decryption fails, it might already be plain text (for migration period)
        return encrypted_value
