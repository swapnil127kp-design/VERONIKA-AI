"""
VERONIKA AI - Sync Server Authentication
Token-based auth for the phone sync server.

Model:
  - A master token is generated once and stored securely (keyring, falling back
    to the config file). Swapnil enters this token in the Android app once.
  - Clients exchange the master token at /api/auth for a short-lived,
    HMAC-signed access token used as `Authorization: Bearer <access_token>`.
"""
import hashlib
import hmac
import logging
import secrets
import time
from typing import Optional, Tuple

from app.config import config

logger = logging.getLogger(__name__)

TOKEN_TTL_SECONDS = 30 * 24 * 3600  # 30 days
_SERVICE = "veronika_ai"
_ACCOUNT = "sync_master_token"


class SyncAuth:
    """Manages the master sync token and HMAC-signed access tokens."""

    def __init__(self):
        self._master_token: Optional[str] = None

    # -- master token ---------------------------------------------

    @property
    def master_token(self) -> str:
        if self._master_token:
            return self._master_token

        # 1) keyring
        try:
            import keyring
            stored = keyring.get_password(_SERVICE, _ACCOUNT)
            if stored:
                self._master_token = stored
                return stored
        except Exception:
            pass

        # 2) config file fallback
        stored = config.get("sync", "master_token", "")
        if stored:
            self._master_token = stored
            return stored

        # 3) generate a fresh one
        token = secrets.token_urlsafe(32)
        self._master_token = token
        config.set("sync", "master_token", token)
        config.save()
        try:
            import keyring
            keyring.set_password(_SERVICE, _ACCOUNT, token)
        except Exception:
            logger.debug("Keyring unavailable; sync token stored in config file")
        logger.info("Generated new sync master token")
        return token

    def rotate_token(self) -> str:
        """Invalidate the old token and issue a new one."""
        self._master_token = None
        try:
            import keyring
            keyring.delete_password(_SERVICE, _ACCOUNT)
        except Exception:
            pass
        config.set("sync", "master_token", "")
        config.save()
        return self.master_token

    # -- access tokens --------------------------------------------

    def _sign(self, payload: str) -> str:
        return hmac.new(
            self.master_token.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def issue_access_token(self, device_name: str = "") -> Tuple[str, int]:
        """Create an HMAC-signed access token. Returns (token, expires_at)."""
        nonce = secrets.token_hex(8)
        expires = int(time.time()) + TOKEN_TTL_SECONDS
        payload = f"{expires}.{nonce}.{device_name}"
        return f"{payload}.{self._sign(payload)}", expires

    def verify_access_token(self, token: str) -> bool:
        """Validate an access token's signature and expiry."""
        if not token or token.count(".") != 3:
            return False
        try:
            expires_str, nonce, device, signature = token.split(".", 3)
            expires = int(expires_str)
        except ValueError:
            return False
        if time.time() > expires:
            return False
        payload = f"{expires_str}.{nonce}.{device}"
        expected = self._sign(payload)
        return hmac.compare_digest(expected, signature)

    def verify_master_token(self, token: str) -> bool:
        if not token:
            return False
        return hmac.compare_digest(self.master_token, token)

    def authenticate(self, token: str) -> Tuple[bool, str]:
        """Accept either the master token or a valid access token.

        Returns (ok, kind) where kind is 'master', 'access', or 'invalid'.
        """
        if not token:
            return False, "invalid"
        if token.count(".") == 3 and self.verify_access_token(token):
            return True, "access"
        if self.verify_master_token(token):
            return True, "master"
        return False, "invalid"
