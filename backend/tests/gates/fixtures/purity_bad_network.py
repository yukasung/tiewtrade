"""ผิดโดยเจตนา: ต่อเครือข่ายด้วย standard library"""
import socket
def connect() -> None:
    socket.create_connection(("example.com", 80))
