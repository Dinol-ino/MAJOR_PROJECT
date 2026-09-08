import os
import base64
import hashlib
import logging
from typing import Literal, Optional, Dict, Any
from cryptography.fernet import Fernet
from sqlalchemy import text

from app.config import settings

logger = logging.getLogger(__name__)

ProviderType = Literal["grok", "zai"]


class APIKeyVault:
    """
    Spec 02 — Secure API Key Vault.
    Provides encrypted persistence and hierarchical resolution for Cloud Fallback LLMs.
    Supported providers: Grok (xAI) and Z.ai only.
    Zero plaintext key exposure in logs, APIs, or responses.
    """

    def __init__(self):
        self._fernet = self._init_fernet()

    def _init_fernet(self) -> Fernet:
        secret = settings.SECRET_KEY.encode("utf-8")
        # Derive a deterministic 32-byte url-safe base64 key from SECRET_KEY
        digest = hashlib.sha256(secret).digest()
        key = base64.urlsafe_b64encode(digest)
        return Fernet(key)

    def _encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def _decrypt(self, ciphertext: str) -> Optional[str]:
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.warning("Decryption of stored credential failed.")
            return None

    def mask(self, key: Optional[str]) -> Optional[str]:
        """
        Produce masked display form for UI/auditing (e.g. 'xai-...9f2a', 'zai-...4b1c').
        Never leaks the full key.
        """
        if not key:
            return None
        key = key.strip()
        if not key:
            return None

        if key.startswith("xai-") and len(key) >= 8:
            return f"xai-...{key[-4:]}"
        if key.startswith("zai-") and len(key) >= 8:
            return f"zai-...{key[-4:]}"

        if len(key) >= 8:
            return f"{key[:3]}...{key[-4:]}"
        return "***"

    def get(self, provider: str) -> Optional[str]:
        """
        Resolve key from priority chain:
        1. Environment variable (.env) -> GROK_API_KEY (or XAI_API_KEY) / ZAI_API_KEY
        2. OS Keyring (if installed and configured)
        3. Database (encrypted Fernet in system_settings table)
        Returns None if no key is configured.
        """
        prov = provider.lower().strip()
        if prov not in ("grok", "zai"):
            return None

        # 1. Environment Variable
        if prov == "grok":
            env_key = os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
            if env_key and env_key.strip():
                return env_key.strip()
        elif prov == "zai":
            env_key = os.getenv("ZAI_API_KEY")
            if env_key and env_key.strip():
                return env_key.strip()

        # 2. OS Keyring (optional, graceful fallback if unavailable)
        try:
            import keyring
            kr_key = keyring.get_password("dfrag_vault", prov)
            if kr_key and kr_key.strip():
                return kr_key.strip()
        except Exception:
            pass

        # 3. Encrypted Database Storage
        try:
            from app.db.engine import get_sync_session
            from app.db.models import SystemSetting
            db_key = f"api_key_{prov}"
            with get_sync_session() as session:
                rec = session.query(SystemSetting).filter_by(key=db_key).first()
                if rec and rec.encrypted_value:
                    decrypted = self._decrypt(rec.encrypted_value)
                    if decrypted and decrypted.strip():
                        return decrypted.strip()
        except Exception as e:
            logger.debug(f"Could not retrieve key for {prov} from DB: {e}")

        return None

    def set_from_ui(self, provider: str, key: str) -> None:
        """
        Encrypt and persist key from UI input into system_settings table and OS keyring.
        Never logs plaintext key.
        """
        prov = provider.lower().strip()
        if prov not in ("grok", "zai"):
            raise ValueError(f"Unsupported provider '{provider}'. Must be 'grok' or 'zai'.")

        clean_key = key.strip()
        if not clean_key:
            self.delete(prov)
            return

        # Encrypt and store in database
        enc_val = self._encrypt(clean_key)
        try:
            from app.db.engine import get_sync_session
            from app.db.models import SystemSetting
            db_key = f"api_key_{prov}"
            with get_sync_session() as session:
                rec = session.query(SystemSetting).filter_by(key=db_key).first()
                if rec:
                    rec.encrypted_value = enc_val
                else:
                    rec = SystemSetting(key=db_key, encrypted_value=enc_val)
                    session.add(rec)
            logger.info(f"API key updated in secure vault for provider: {prov}")
        except Exception as e:
            logger.error(f"Failed to persist encrypted credential to database: {e}")
            raise

        # Attempt to save to OS keyring
        try:
            import keyring
            keyring.set_password("dfrag_vault", prov, clean_key)
        except Exception:
            pass

    def delete(self, provider: str) -> None:
        """Removes key for the given provider."""
        prov = provider.lower().strip()
        db_key = f"api_key_{prov}"
        try:
            from app.db.engine import get_sync_session
            from app.db.models import SystemSetting
            with get_sync_session() as session:
                rec = session.query(SystemSetting).filter_by(key=db_key).first()
                if rec:
                    session.delete(rec)
        except Exception as e:
            logger.debug(f"Failed to delete DB key for {prov}: {e}")

        try:
            import keyring
            keyring.delete_password("dfrag_vault", prov)
        except Exception:
            pass

    def is_configured(self, provider: str) -> bool:
        return bool(self.get(provider))

    def get_status(self) -> Dict[str, Any]:
        """
        Returns transparent configuration status with masked keys for display.
        """
        grok_key = self.get("grok")
        zai_key = self.get("zai")

        return {
            "enabled": settings.cloud_fallback.enabled,
            "auto_fallback": settings.cloud_fallback.auto_fallback,
            "active_provider": settings.cloud_fallback.active_provider,
            "grok_configured": bool(grok_key),
            "zai_configured": bool(zai_key),
            "grok_masked": self.mask(grok_key),
            "zai_masked": self.mask(zai_key),
            "grok_model": settings.cloud_fallback.grok_model,
            "zai_model": settings.cloud_fallback.zai_model,
        }

    def update_settings(
        self,
        enabled: Optional[bool] = None,
        auto_fallback: Optional[bool] = None,
        active_provider: Optional[str] = None
    ) -> None:
        """Updates runtime cloud fallback configuration flags."""
        if enabled is not None:
            settings.cloud_fallback.enabled = enabled
        if auto_fallback is not None:
            settings.cloud_fallback.auto_fallback = auto_fallback
        if active_provider is not None:
            clean_prov = active_provider.lower().strip()
            if clean_prov in ("grok", "zai"):
                settings.cloud_fallback.active_provider = clean_prov


api_vault = APIKeyVault()
