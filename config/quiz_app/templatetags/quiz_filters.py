from django import template

register = template.Library()

@register.filter
def get_letter(value):
    """Convert 1 -> A, 2 -> B, 3 -> C ..."""
    try:
        return chr(64 + int(value))
    except (ValueError, TypeError):
        return value
    
@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)
