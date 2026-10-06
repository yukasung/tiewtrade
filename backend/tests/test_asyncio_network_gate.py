"""Asyncio networking is confined to the existing transport gateway (V-32.1)."""

from pathlib import Path

import pytest

from tests.money_movement import check_tree
from tests.venue_isolation import check_network_only_in

UNSAFE = [
    "import asyncio\nasyncio.open_connection(host, 443, ssl=True)",
    "import asyncio as aio\naio.start_server(callback, host, 443)",
    "from asyncio import open_connection as dial\ndial(host, 443)",
    "from asyncio.streams import open_unix_connection\nopen_unix_connection(path)",
    "import asyncio.streams as streams\nstreams.start_unix_server(callback, path)",
    "import asyncio\nnetwork = asyncio\ndial = network.open_connection\ndial(host, 443)",
    "import asyncio\nloop = asyncio.get_running_loop()\nloop.create_connection(factory, host, 443)",
    "from asyncio import get_event_loop as current\nloop = current()\n"
    "other = loop\nother.create_datagram_endpoint(factory, remote_addr=address)",
    "import asyncio\nasyncio.new_event_loop().getaddrinfo(host, 443)",
    "from asyncio.events import get_running_loop\nget_running_loop().sock_connect(sock, address)",
    "import asyncio\nloop: asyncio.AbstractEventLoop\nloop.start_tls(transport, protocol, context)",
    "from asyncio import AbstractEventLoop as Loop\n"
    "def send(loop: Loop):\n loop.sock_sendall(sock, data)",
    "import asyncio\nwith asyncio.Runner() as runner:\n"
    " loop = runner.get_loop()\n loop.create_server(factory, host, 443)",
    "import asyncio\npolicy = asyncio.get_event_loop_policy()\n"
    "loop = policy.new_event_loop()\nloop.getnameinfo(address)",
    "import asyncio\ndef send(loop, /):\n loop.create_unix_connection(factory, path)\n"
    "send(asyncio.get_running_loop())",
    "import asyncio\ndef current():\n return asyncio.get_running_loop()\n"
    "loop = current()\nloop.connect_accepted_socket(factory, sock)",
    "import asyncio\nstate.loop = asyncio.get_event_loop()\nstate.loop.sock_recv(sock, 100)",
    "from asyncio import *\nopen_connection(host, 443)",
    "import asyncio\nwith asyncio.Runner() as runner:\n"
    " current = runner.get_loop\n current().create_connection(factory, host, 443)",
    "import asyncio\npolicy = asyncio.get_event_loop_policy()\n"
    "current = policy.get_event_loop\ncurrent().getaddrinfo(host, 443)",
    "import asyncio\ndef current():\n return asyncio.get_running_loop()\n"
    "loop_for = current\nloop_for().create_connection(factory, host, 443)",
    *(
        f"import asyncio\nloop = {expression}\n"
        "other = loop\nother.create_connection(factory, host, 443)"
        for expression in (
            "existing_loop or asyncio.get_running_loop()",
            "asyncio.get_running_loop() or existing_loop",
            "enabled and asyncio.get_running_loop()",
            "asyncio.get_running_loop() and existing_loop",
            "existing_loop if existing_loop is not None else asyncio.get_running_loop()",
            "asyncio.get_running_loop() if enabled else existing_loop",
            "existing_loop or (asyncio.get_running_loop() if enabled else fallback)",
        )
    ),
    "import asyncio\n(existing_loop or asyncio.get_running_loop()).sock_connect(sock, address)",
    "import asyncio\ndef current():\n"
    " return existing_loop if ready else asyncio.get_running_loop()\n"
    "current().getaddrinfo(host, 443)",
    "import asyncio\ndef outer():\n loop = asyncio.get_running_loop()\n"
    " def inner():\n  loop.create_connection(factory, host, 443)\n inner()",
    "import asyncio\ndef first():\n def current():\n  return metadata\n"
    " current().create_connection()\ndef second():\n def current():\n"
    "  return asyncio.get_running_loop()\n current().create_connection(factory, host, 443)",
    "import asyncio\ndef setup():\n global client\n client = asyncio.get_running_loop()\n"
    "def send():\n client.create_connection(factory, host, 443)",
    "import asyncio\ndef outer():\n client = metadata\n def setup():\n"
    "  nonlocal client\n  client = asyncio.get_running_loop()\n"
    " client.create_connection(factory, host, 443)",
    "import asyncio\nclass Client:\n def __init__(self):\n"
    "  self.loop = asyncio.get_running_loop()\n def connect(self):\n"
    "  self.loop.create_connection(factory, host, 443)",
    "import asyncio\ndef send(asyncio: asyncio.AbstractEventLoop):\n"
    " asyncio.create_connection(factory, host, 443)",
    *(
        f"import asyncio\nloop = asyncio.get_running_loop()\ndef send():\n items = {expression}\n"
        " loop.create_connection(factory, host, 443)"
        for expression in (
            "[loop for loop in metadata]",
            "{loop for loop in metadata}",
            "{loop: loop for loop in metadata}",
            "(loop for loop in metadata)",
        )
    ),
    *(
        f"import asyncio\nloop = asyncio.get_running_loop()\ndef send():\n items = {expression}"
        for expression in (
            "[loop for loop in loop.getaddrinfo(host, 443)]",
            "{loop for loop in loop.getaddrinfo(host, 443)}",
            "{loop: loop for loop in loop.getaddrinfo(host, 443)}",
            "(loop for loop in loop.getaddrinfo(host, 443))",
        )
    ),
    "import asyncio\nloop = asyncio.get_running_loop()\n"
    "items = [loop.create_connection(factory, host, 443) "
    "for item in metadata for value in [loop for loop in metadata]]",
    *(
        "import asyncio\nclass Base:\n def __init__(self):\n"
        "  self.loop = asyncio.get_running_loop()\n"
        f"{ancestry}\n def send(self):\n  self.loop.create_connection(factory, host, 443)"
        for ancestry in (
            "class Client(Base):",
            "class Middle(Base):\n pass\nclass Client(Middle):",
            "class Other:\n pass\nclass Client(Other, Base):",
        )
    ),
    "import asyncio\nclass Base:\n @classmethod\n def setup(cls):\n"
    "  cls.loop = asyncio.get_running_loop()\nclass Client(Base):\n"
    " @classmethod\n def send(cls):\n  cls.loop.create_connection(factory, host, 443)",
    "import asyncio\nclass Root:\n def __init__(self):\n  self.loop = metadata\n"
    "class Left(Root):\n pass\nclass Right(Root):\n def __init__(self):\n"
    "  self.loop = asyncio.get_running_loop()\nclass Client(Left, Right):\n"
    " def send(self):\n  self.loop.create_connection(factory, host, 443)",
    "import asyncio\nclass Base:\n def __init__(self):\n"
    "  self.loop = asyncio.get_running_loop()\nclass Client(Base):\n"
    " def send(self):\n  self.loop: Any\n"
    "  self.loop.create_connection(factory, host, 443)",
    "import asyncio\nclass Base:\n def __init__(self):\n  self.loop = metadata\n"
    "class Client(Base):\n def send(self):\n  self.loop: asyncio.AbstractEventLoop\n"
    "  self.loop.create_connection(factory, host, 443)",
    *(
        "import asyncio\nclass Base:\n def __init__(self):\n"
        "  self.loop = asyncio.get_running_loop()\nclass Client(Base):\n"
        f"{assignment}\n def send(self):\n  self.loop.create_connection(factory, host, 443)"
        for assignment in (
            " def set_loop(self, replacement):\n  self.loop = replacement",
            " def set_loop(self):\n  self.loop = asyncio.Runner()",
            " def __init__(self):\n  super().__init__()\n  if replace:\n   self.loop = metadata",
        )
    ),
]

SAFE = """
import asyncio as aio
from asyncio import sleep as wait, AbstractEventLoop as Loop

def schedule(loop: Loop):
    loop.call_soon(callback)
    loop.create_task(coro)

async def work():
    loop = aio.get_running_loop()
    schedule(loop)
    await wait(1)
    await aio.gather(coro, coro)

with aio.Runner() as runner:
    loop = runner.get_loop()
    loop.call_later(1, callback)
    current = runner.get_loop
    current().create_task(coro)

policy = aio.get_event_loop_policy()
new_loop = policy.new_event_loop
new_loop().call_soon(callback)

def other_object():
    def hidden_loop():
        return aio.get_running_loop()
    return metadata

other_object().create_connection()

aio.run(work())
metadata.create_connection()

selected = metadata if ready else fallback
(selected or fallback).create_connection()
(existing_loop or aio.get_running_loop()).create_task(coro)
(aio.get_running_loop() if ready else fallback).call_soon(callback)
"""


SAFE_SCOPES = [
    "import asyncio\ndef first():\n client = asyncio.get_running_loop()\n"
    " client.create_task(coro)\ndef second():\n client = metadata\n client.create_connection()",
    "import asyncio\ndef schedule(client: asyncio.AbstractEventLoop):\n"
    " client.create_task(coro)\ndef second(client):\n client.create_connection()",
    "def first():\n import asyncio as client\n client.run(coro)\n"
    "def second(client):\n client.open_connection()",
    "import asyncio\ndef first():\n def current():\n"
    "  return asyncio.get_running_loop()\n current().create_task(coro)\n"
    "def second():\n def current():\n  return metadata\n current().create_connection()",
    "import asyncio\nclient = asyncio.get_running_loop()\n"
    "def second(client):\n client.create_connection()",
    "import asyncio\ndef first():\n client = asyncio.get_running_loop()\n"
    " def second(client):\n  client.create_connection()\n client.create_task(coro)",
    "import asyncio\ndef schedule(client):\n client.create_task(coro)\n"
    "schedule(asyncio.get_running_loop())\ndef second(client):\n client.create_connection()",
    "import asyncio\nclass Scheduler:\n def __init__(self):\n"
    "  self.loop = asyncio.get_running_loop()\n def schedule(self):\n"
    "  self.loop.create_task(coro)\nclass Client:\n def connect(self):\n"
    "  self.loop.create_connection()",
    *(
        f"import asyncio\nloop = asyncio.get_running_loop()\nitems = {expression}\n"
        "loop.create_task(coro)"
        for expression in (
            "[loop.create_connection() for loop in metadata]",
            "{loop.create_connection() for loop in metadata}",
            "{loop: loop.create_connection() for loop in metadata}",
            "(loop.create_connection() for loop in metadata)",
        )
    ),
    "import asyncio\nclass Base:\n def __init__(self):\n"
    "  self.loop = asyncio.get_running_loop()\nclass Client(Base):\n"
    " def __init__(self):\n  self.loop = metadata\n"
    " def send(self):\n  self.loop.create_connection()",
    "import asyncio\nclass First:\n def __init__(self):\n  self.loop = metadata\n"
    "class Second:\n def __init__(self):\n  self.loop = asyncio.get_running_loop()\n"
    "class Client(First, Second):\n def send(self):\n  self.loop.create_connection()",
    "import asyncio\nclass Root:\n def __init__(self):\n"
    "  self.loop = asyncio.get_running_loop()\nclass Left(Root):\n pass\n"
    "class Right(Root):\n def __init__(self):\n  self.loop = metadata\n"
    "class Client(Left, Right):\n def send(self):\n  self.loop.create_connection()",
]


@pytest.mark.parametrize("source", UNSAFE)
@pytest.mark.parametrize("relative", ["services/engine/main.py", "infra/shortcut.py"])
def test_global_gate_rejects_asyncio_networking(
    tmp_path: Path,
    source: str,
    relative: str,
) -> None:
    target = tmp_path / "tiewtrade" / relative
    target.parent.mkdir(parents=True)
    target.write_text(source)
    found = check_tree(tmp_path)
    assert found, source
    assert all(item.kind == "network-outside-gateway" and item.path == target for item in found)


@pytest.mark.parametrize("source", UNSAFE)
def test_adapter_gate_rejects_asyncio_networking(tmp_path: Path, source: str) -> None:
    target = tmp_path / "shortcut.py"
    target.write_text(source)
    found = check_network_only_in(tmp_path, "transport")
    assert found, source
    assert all(item.kind == "network-outside-gateway" and item.path == target for item in found)


@pytest.mark.parametrize("source", [SAFE, *SAFE_SCOPES])
def test_scheduling_and_gateway_are_allowed(tmp_path: Path, source: str) -> None:
    target = tmp_path / "tiewtrade/services/engine/main.py"
    target.parent.mkdir(parents=True)
    target.write_text(source)
    assert check_tree(tmp_path) == []
    adapter = tmp_path / "tiewtrade/venues/example"
    adapter.mkdir(parents=True)
    (adapter / "__init__.py").write_text("")
    (adapter / "transport.py").write_text(UNSAFE[0])
    (adapter / "schedule.py").write_text(source)
    assert check_network_only_in(adapter, "transport") == []
    assert check_tree(tmp_path) == []
