def clamp(value, low, high):
    """Clamp a number to an inclusive interval; reject reversed bounds."""
    if low > high:
        raise ValueError("low exceeds high")
    return min(high, max(low, value))

