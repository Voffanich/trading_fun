def r_signif(number: float, precision: int) -> float:
    """Function rounds the given float number with 0 in integer part to float number with N significant figures required.
    If given the number with integer part > 0, returns the number rounded to N - 1 figures after comma.

    Args:
        number (float): float number which abs(number) < 1 needed to be rounded
        precision (int): quantity of signigicant figures needed after rounding

    Returns:
        float: rounded to 'precision' significant figures 'number'
    """
    zero_counter = 0
    check_number = number
    
    if abs(check_number) >= 1:
        return round(number, precision - 1)
    else:
        while True:
            check_number *=10
            if abs(check_number) < 1:
                zero_counter += 1
            else:
                break
    
    return round(number, zero_counter + precision)