"""ผิดโดยเจตนา: อ่านไฟล์"""
def load() -> str:
    with open("config.txt") as handle:
        return handle.read()
