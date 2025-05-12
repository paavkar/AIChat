from django import template

register = template.Library()

@register.filter(name='div_by')
def div_by(value, divisor):
    try:
        return float(value) / float(divisor)
    except (ValueError, ZeroDivisionError):
        return None