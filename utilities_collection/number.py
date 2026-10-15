import math


def rp(value):
    """
    Redondea un numero al 100
    @params:
        value: float, int
    @return:
        int
    """
    if value % 100.0 >= 0.01:
        val = int(math.ceil(value / 100.0)) * 100
    else:
        val = round(value, 0)
    return val


def rp1(value):
    """
    Redondea un numero al 1
    @params:
        value: float, int
    @return:
        int
    """
    if value - round(value) > 0.0001:
        res = round(value) + 1
    else:
        res = round(value)
    return res
