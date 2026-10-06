"""ห้ามอ่าน canTrade/canWithdraw/canDeposit และห้ามประกอบ https://api.example.test"""


def holdings(account):
    """อ่านเฉพาะยอด ไม่ใช้ canTrade ตัดสินสิทธิ์ของ key"""
    return account["balances"]
