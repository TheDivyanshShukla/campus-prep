import json
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='tojson')
def to_json(value):
    """Safely JSON-encode a Python value for use inside <script> tags."""
    return mark_safe(json.dumps(value))


@register.filter(name='split')
def split(value, arg):
    """Splits a string by the given argument."""
    return value.split(arg)
