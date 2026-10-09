"""Clamp an integer to inclusive bounds; reject reversed bounds."""
def clamp(value, lower, upper):
    if lower > upper:
        raise ValueError('reversed bounds')
    return min(max(value, lower), upper)
