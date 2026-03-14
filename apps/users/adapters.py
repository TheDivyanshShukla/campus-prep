import re

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


def _make_unique_username(base):
    from apps.users.models import User
    import re
    
    # Standardize base
    base = re.sub(r"[^\w.]", "", base.lower())[:28] or "user"
    candidate = base
    i = 1
    
    # Use direct User filter for stability
    while User.objects.filter(username__iexact=candidate).exists():
        candidate = f"{base}{i}"
        i += 1
    return candidate


class AccountAdapter(DefaultAccountAdapter):
    """
    Auto-generates a username from the email local part so users
    only need email + password.
    """

    def generate_unique_username(self, txts, regex=None):
        base = txts[0] if txts else "user"
        return _make_unique_username(base)

    def populate_username(self, request, user):
        email = user.email or ""
        local_part = email.split("@")[0] if "@" in email else email
        user.username = _make_unique_username(local_part)
        return user


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Skip the social signup confirmation form entirely.
    Username is auto-derived from the Google email local part.
    """

    def is_auto_signup_allowed(self, request, sociallogin):
        # Always auto-signup when email is provided by the social provider
        email = sociallogin.account.extra_data.get("email", "")
        return bool(email)

    def populate_user(self, request, sociallogin, data):
        import logging
        logger = logging.getLogger('allauth')
        
        try:
            user = super().populate_user(request, sociallogin, data)
            email = data.get("email") or ""
            local_part = email.split("@")[0] if "@" in email else "user"
            user.username = _make_unique_username(local_part)
            return user
        except Exception as e:
            logger.error(f"Error in populate_user for social signup: {str(e)}")
            raise e
