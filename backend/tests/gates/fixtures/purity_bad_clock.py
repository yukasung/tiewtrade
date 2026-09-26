"""ผิดโดยเจตนา: อ่านนาฬิกา"""
from datetime import datetime
def now() -> str:
    return datetime.now().isoformat()
