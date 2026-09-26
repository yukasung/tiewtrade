"""ผิดโดยเจตนา: อ่านนาฬิกาโดย import ฟังก์ชันมาตรง ๆ — ต้องไม่หลุด (รีวิว S-1)"""
from time import time


def now() -> float:
    return time()
