"""ผิดโดยเจตนา: อ่านนาฬิกาผ่าน alias — ต้องไม่หลุด (รีวิว S-1)"""
from datetime import datetime as dt


def now() -> str:
    return dt.now().isoformat()
