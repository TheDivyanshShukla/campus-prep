"""
Cloudflare Turnstile verification service.
Handles verification of Turnstile tokens for bot protection.
"""

import os
import httpx
import logging

logger = logging.getLogger(__name__)


class TurnstileService:
    """Service for verifying Cloudflare Turnstile tokens."""
    
    VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    
    def __init__(self):
        self.secret_key = os.getenv('CLOUDFLARE_TURNSTILE_SECRET_KEY')
        self.site_key = os.getenv('CLOUDFLARE_TURNSTILE_SITE_KEY')
        self.enabled = bool(self.secret_key and self.site_key)
    
    def verify_token(self, token: str, remote_ip: str = None) -> tuple[bool, str]:
        """
        Verify a Turnstile token.
        
        Args:
            token: The Turnstile token from the frontend
            remote_ip: Optional IP address of the client
        
        Returns:
            tuple: (is_valid: bool, message: str)
        """
        if not self.enabled:
            logger.warning("Turnstile is not enabled. Check environment variables.")
            return False, "Turnstile configuration missing"
        
        if not token:
            return False, "No Turnstile token provided"
        
        try:
            payload = {
                "secret": self.secret_key,
                "response": token,
            }
            
            if remote_ip:
                payload["remoteip"] = remote_ip
            
            with httpx.Client() as client:
                response = client.post(self.VERIFY_URL, data=payload, timeout=10.0)
                response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                logger.info("Turnstile verification successful")
                return True, "Verification successful"
            else:
                error_codes = result.get("error-codes", [])
                error_message = ", ".join(error_codes) if error_codes else "Unknown error"
                logger.warning(f"Turnstile verification failed: {error_message}")
                return False, f"Verification failed: {error_message}"
        
        except httpx.RequestError as e:
            logger.error(f"Turnstile request error: {str(e)}")
            return False, "Could not verify token (network error)"
        except Exception as e:
            logger.error(f"Unexpected error during Turnstile verification: {str(e)}")
            return False, "Could not verify token (server error)"
    
    def get_site_key(self) -> str:
        """Get the Turnstile site key for frontend use."""
        return self.site_key or ""


# Singleton instance
turnstile_service = TurnstileService()
