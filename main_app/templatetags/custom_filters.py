"""
Custom template tags and filters for the ERP system
"""
from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Get an item from a dictionary using a key.
    Usage in template: {{ my_dict|get_item:my_key }}
    """
    if dictionary is None:
        return None
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter(name='get_attr')
def get_attr(obj, attr):
    """
    Get an attribute from an object.
    Usage in template: {{ my_obj|get_attr:'attribute_name' }}
    """
    if obj is None:
        return None
    return getattr(obj, attr, None)


@register.filter(name='add_str')
def add_str(value, arg):
    """
    Concatenate two strings.
    Usage in template: {{ "hello"|add_str:"_world" }}
    """
    return str(value) + str(arg)
