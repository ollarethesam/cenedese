"""
core_tags.py — Custom template filters.

These expose Python utility functions to Django templates so we can
keep logic out of templates and avoid duplicating it.
"""
from django import template
from core.utils import get_bagno_color_class, get_active_flags

register = template.Library()


@register.filter
def color_class(bagno):
    """
    Template filter: {{ bagno|color_class }}
    Returns the CSS colour class string for a bagno (e.g. "azzurro", "verde").
    """
    return get_bagno_color_class(bagno)


@register.filter
def active_flags(obj):
    """
    Template filter: {{ bagno|active_flags }}
    Returns a comma-separated string of active processing flag labels.
    """
    return get_active_flags(obj)


@register.filter
def split(value, delimiter=","):
    """
    Template filter: {{ "a,b,c"|split:"," }}
    Splits a string by delimiter — used in templates to iterate over static lists.
    """
    return [item.strip() for item in value.split(delimiter)]
