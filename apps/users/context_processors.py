"""
Context processors for the users app.
Exposes commonly needed variables to all templates.
"""

from django.conf import settings
from apps.common.turnstile import turnstile_service


def turnstile(request):
    """
    Exposes Cloudflare Turnstile configuration to templates.
    """
    return {
        'TURNSTILE_SITE_KEY': turnstile_service.get_site_key(),
        'TURNSTILE_ENABLED': settings.TURNSTILE_ENABLED,
    }
