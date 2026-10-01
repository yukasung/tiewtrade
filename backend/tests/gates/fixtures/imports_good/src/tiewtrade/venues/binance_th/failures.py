"""การแปลข้อผิดพลาด — ห้ามรู้จักเครือข่าย"""


def translate(status: int) -> str:
    return "rejected" if status else "ok"
