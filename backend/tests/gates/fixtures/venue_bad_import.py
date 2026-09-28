"""ผิดโดยเจตนา: import ชื่อ module ของตลาดตรง ๆ จากนอกชั้น venue"""

from binance import Client


def make() -> object:
    return Client
