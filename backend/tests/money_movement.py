"""ด่าน: โค้ดต้องไปถึง endpoint ที่ย้ายเงินออกจากบัญชีผู้ใช้ไม่ได้ (F-07 RQ-16)

**ทำไมต้องมีด่านนี้ทั้งที่ไม่มีใครตั้งใจเขียนโค้ดถอนเงิน** — NC-16 ยังเปิดอยู่:
เราไม่รู้ว่า API key ของตลาดนี้ถอนเงินได้หรือไม่ และผู้ใช้ไม่มีช่องให้ปิดสิทธิ์นั้น
สิ่งที่เรากันได้จริงจึงไม่ใช่ "สิทธิ์ของ key" แต่คือ **ความสามารถของโค้ดเราเอง**
(`trading-safety.md` หัวข้อ 2 · `requirements.md` RQ-16)

**ชั้นที่บังคับจริงคือชนิดข้อมูล** — ตัวส่งคำขอรับเฉพาะสมาชิกของ `Endpoint`
ฉะนั้นเส้นทางที่ไม่ได้ประกาศไว้ **สร้างขึ้นมาไม่ได้** ไฟล์นี้คือชั้นที่สองกับสาม:
ตรวจว่าไม่มีใครประกาศสมาชิกที่ย้ายเงิน และไม่มีสตริงของเส้นทางเหล่านั้นหลงเหลืออยู่

**ด่านค้นสตริงอย่างเดียวพิสูจน์อะไรไม่ได้** เส้นทางที่ประกอบจากตัวแปรจะผ่านมันไปได้
— เขียนไว้ตรงนี้เพื่อไม่ให้ใครอ่านด่านนี้แล้วเข้าใจว่ามันคือการป้องกันทั้งหมด
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.purity import Violation
from tests.venue_isolation import (
    adapter_packages,
    check_asyncio_network,
    check_vocabulary,
    code_nodes,
    network_imports,
)

#: ชิ้นส่วนของเส้นทางที่ย้ายเงินออกจากบัญชีผู้ใช้ หรือย้ายระหว่างบัญชี
#:
#: เขียนเป็นชิ้นส่วน ไม่ใช่เส้นทางเต็ม เพราะตลาดเปลี่ยนรุ่นของ path ได้
#: (`/api/v1/...` เป็น `/api/v3/...`) แล้วรายการที่จำเส้นทางเต็มจะพลาดทันที
FORBIDDEN_PATH_FRAGMENTS: frozenset[str] = frozenset(
    {
        "withdraw",
        "transfer",
        "sub-account",
        "subaccount",
        "universal",
    }
)


#: สถานะบัญชี ไม่ใช่สิทธิ์ของ key — ห้ามใช้ในโค้ดจริงทั้งในและนอก venues (V-33)
ACCOUNT_FLAGS = frozenset({"cantrade", "canwithdraw", "candeposit"})

#: hostname ที่อาจนำไปประกอบ URL ในตัวเชื่อม (V-32.1)
_HOSTNAME = re.compile(r"(?:[a-z0-9-]+\.)+[a-z]{2,}(?::\d+)?$")


def _offending_fragment(text: str) -> str | None:
    """ชิ้นส่วนต้องห้ามที่พบในข้อความที่อาจกลายเป็นเส้นทาง

    จับสองรูป:

    1. **ข้อความที่ขึ้นต้นด้วย `/`** และมีชิ้นส่วนต้องห้ามอยู่ข้างใน — เส้นทางที่เขียนตรง ๆ
    2. **ข้อความที่ *เท่ากับ* ชิ้นส่วนต้องห้ามพอดี** — ชิ้นส่วนที่รอประกอบเป็นเส้นทาง
       (`f"{prefix}/{action}"`) ซึ่งรูปแรกมองไม่เห็น

    **ไม่จับคำที่โผล่กลางข้อความธรรมดา** เช่นคำอธิบายภาษาไทยที่พูดถึงการโอนเงิน
    เพราะด่านที่ดังผิดบ่อยคือด่านที่คนเลิกเชื่อ ซึ่งแย่กว่าไม่มีด่าน

    **ยังมีช่องที่รูปนี้มองไม่เห็น** เช่นการต่อสตริงทีละตัวอักษร — เป็นเหตุผลที่
    ชั้นที่บังคับจริงคือชนิดข้อมูลของ `Endpoint` ไม่ใช่ด่านนี้
    """
    lowered = text.lower()
    if lowered in FORBIDDEN_PATH_FRAGMENTS:
        return lowered
    if not text.startswith("/"):
        return None
    for fragment in sorted(FORBIDDEN_PATH_FRAGMENTS):
        if fragment in lowered:
            return fragment
    return None


def check_no_money_paths(path: Path) -> list[Violation]:
    """ไฟล์นี้ต้องไม่มีสตริงของเส้นทางที่ย้ายเงิน"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        fragment = _offending_fragment(node.value)
        if fragment is not None:
            violations.append(
                Violation(
                    path,
                    node.lineno,
                    "money-moving-path",
                    f"เส้นทางที่ย้ายเงิน ({fragment!r}) ปรากฏในโค้ด",
                )
            )

    return violations


def _account_schema_literals(path: Path) -> frozenset[tuple[int, int]]:
    """NC-19 permits names only in the approved immutable account-schema declaration."""
    if path.parts[-4:] != ("tiewtrade", "venues", "binance_th", "mapping.py"):
        return frozenset()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    expected = {
        "makerCommission",
        "takerCommission",
        "buyerCommission",
        "sellerCommission",
        "canTrade",
        "canWithdraw",
        "canDeposit",
        "updateTime",
        "balances",
    }
    declarations = [
        node
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "_ACCOUNT_FIELDS"
    ]
    if len(declarations) != 1:
        return frozenset()
    value = declarations[0].value
    if not (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "frozenset"
        and len(value.args) == 1
        and not value.keywords
        and isinstance(value.args[0], ast.Set)
    ):
        return frozenset()
    members = value.args[0].elts
    if len(members) != len(expected) or any(not isinstance(item, ast.Constant) for item in members):
        return frozenset()
    literals = [item for item in members if isinstance(item, ast.Constant)]
    if any(not isinstance(item.value, str) for item in literals):
        return frozenset()
    if {item.value for item in literals} != expected:
        return frozenset()
    return frozenset((item.lineno, item.col_offset) for item in literals)


def check_tree(root: Path) -> list[Violation]:
    """ตรวจเส้นทางและ flag ทุกไฟล์ · ตัวเชื่อมต้องออกเครือข่ายทาง transport เท่านั้น"""
    violations: list[Violation] = []
    adapters = adapter_packages(root / "tiewtrade" / "venues")
    gateways = {adapter / "transport.py" for adapter in adapters}
    # F-10 approves this public WSS gateway only, not an extra gateway per adapter.
    stream_gateway = root / "tiewtrade/venues/binance_th/stream_transport.py"
    gateways.add(stream_gateway)
    for path in sorted(root.rglob("*.py")):
        violations.extend(check_no_money_paths(path))
        if path == stream_gateway:
            violations.extend(
                Violation(
                    path,
                    node.lineno,
                    "network-outside-gateway",
                    "WSS gateway allows websockets only",
                )
                for module, node in network_imports(path)
                if module.split(".")[0] != "websockets"
            )
        violations.extend(
            Violation(item.path, item.line, "account-flag", item.detail)
            for item in check_vocabulary(
                path, ACCOUNT_FLAGS, allowed_literals=_account_schema_literals(path)
            )
            if item.kind == "venue-word"
        )
        if path not in gateways:
            relative = path.relative_to(root).as_posix()
            violations.extend(check_network_boundary(path, relative))
            violations.extend(
                check_no_market_urls(path, fragments=any(path.is_relative_to(a) for a in adapters))
            )
    return violations


def check_no_market_urls(path: Path, *, fragments: bool = True) -> list[Violation]:
    """จับ URL/ชิ้นส่วน URL และการอ่าน BASE_URL รวม alias · re-export ยังทำได้"""
    nodes = code_nodes(path)
    parents = {id(child): node for node in nodes for child in ast.iter_child_nodes(node)}
    base_names = {"BASE_URL"}
    for node in nodes:
        if isinstance(node, ast.ImportFrom):
            base_names.update(
                alias.asname or alias.name for alias in node.names if alias.name == "BASE_URL"
            )

    violations: list[Violation] = []
    origin_prefixes = _origin_prefix_literals(path)
    for node in nodes:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if (node.lineno, node.col_offset) in origin_prefixes:
                continue
            value = node.value.lower()
            forbidden = (
                value.startswith(("http://", "https://", "ws://", "wss://", "//"))
                or (
                    value in {"http", "https", "ws", "wss", "http:", "https:", "ws:", "wss:", "://"}
                    and (
                        fragments
                        or isinstance(parents.get(id(node)), (ast.Assign, ast.BinOp, ast.JoinedStr))
                    )
                )
                or (fragments and _HOSTNAME.fullmatch(value) is not None)
            )
        elif isinstance(node, ast.Name):
            forbidden = isinstance(node.ctx, ast.Load) and node.id in base_names
        elif isinstance(node, ast.Attribute):
            forbidden = isinstance(node.ctx, ast.Load) and node.attr == "BASE_URL"
        else:
            continue
        if forbidden:
            violations.append(
                Violation(
                    path,
                    node.lineno,
                    "market-url-outside-gateway",
                    "ประกอบหรืออ่าน URL นอก transport ของตัวเชื่อม",
                )
            )
    return violations


def _origin_prefix_literals(path: Path) -> frozenset[tuple[int, int]]:
    """F-10 origin validation may compare HTTP prefixes, never construct endpoints."""
    if path.parts[-4:] != ("tiewtrade", "services", "api", "settings.py"):
        return frozenset()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    prefixes: set[tuple[int, int]] = set()
    for function in tree.body:
        if not isinstance(function, ast.FunctionDef) or function.name != "price_origins":
            continue
        for node in ast.walk(function):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "startswith"
                and len(node.args) == 1
                and not node.keywords
                and isinstance(node.args[0], ast.Tuple)
            ):
                continue
            members = node.args[0].elts
            if len(members) == 2 and all(isinstance(item, ast.Constant) for item in members):
                literals = [item for item in members if isinstance(item, ast.Constant)]
                if [item.value for item in literals] == ["http://", "https://"]:
                    prefixes.update((item.lineno, item.col_offset) for item in literals)
    return frozenset(prefixes)


def check_network_boundary(path: Path, relative: str) -> list[Violation]:
    """NC-17: import นอก gateway ต้องตรงข้อยกเว้นทั้งไฟล์และสมาชิก"""
    allowed: dict[str, str] = {}
    if relative in {"tiewtrade/services/engine/main.py", "tiewtrade/services/market_data/main.py"}:
        allowed = {"httpx": "AsyncClient", "socket": "gethostname"}
    elif relative == "tiewtrade/infra/auth/totp.py":
        allowed = {"urllib.parse": "quote"}
    elif relative == "tiewtrade/services/api/price_protocol.py":
        # NC-29: inbound Sans-I/O decoding only, not a network-client gateway.
        allowed = {"websockets.server": "ServerProtocol", "websockets.frames": "CloseCode"}
    violations = check_asyncio_network(path)
    bindings: dict[str, tuple[str, str | None]] = {}
    for module, node in network_imports(path):
        member = allowed.get(module)
        approved = member is not None and (
            (isinstance(node, ast.Import) and module in {"httpx", "socket"})
            or (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and all(alias.name == member for alias in node.names)
            )
        )
        if not approved:
            violations.append(
                Violation(
                    path,
                    node.lineno,
                    "network-outside-gateway",
                    "import เครือข่ายนอก gateway ที่ไม่อยู่ในข้อยกเว้น",
                )
            )
            continue
        for alias in node.names:
            if isinstance(node, ast.Import) and alias.name != module:
                continue
            bindings[alias.asname or alias.name] = (
                module,
                member if isinstance(node, ast.ImportFrom) else None,
            )
    if bindings:
        violations.extend(_check_composition_uses(path, bindings, allowed))
    return violations


def _check_composition_uses(
    path: Path, bindings: dict[str, tuple[str, str | None]], allowed: dict[str, str]
) -> list[Violation]:
    nodes = code_nodes(path)
    parents = {id(child): node for node in nodes for child in ast.iter_child_nodes(node)}
    annotations = {
        id(child)
        for node in nodes
        if isinstance(node, ast.arg) and node.annotation
        for child in ast.walk(node.annotation)
    }

    def member_of(node: ast.AST) -> tuple[str, str] | None:
        if isinstance(node, ast.Name) and node.id in bindings:
            module, member = bindings[node.id]
            return (module, member) if member else None
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            binding = bindings.get(node.value.id)
            if binding and binding[1] is None:
                return binding[0], node.attr
        return None

    violations: list[Violation] = []
    for node in nodes:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if node.value is not None and any(
                isinstance(target, ast.Name) and target.id == "__all__" for target in targets
            ):
                exported = {
                    child.value
                    for child in ast.walk(node.value)
                    if isinstance(child, ast.Constant) and isinstance(child.value, str)
                }
                if any(
                    name in exported and module.startswith("websockets.")
                    for name, (module, _member) in bindings.items()
                ):
                    violations.append(
                        Violation(
                            path,
                            node.lineno,
                            "network-outside-gateway",
                            "ห้าม re-export decoder imports",
                        )
                    )
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in bindings:
            module, member = bindings[node.id]
            parent = parents.get(id(node))
            if member is None:
                valid = isinstance(parent, ast.Attribute) and parent.attr == allowed[module]
            elif (module, member) == ("websockets.server", "ServerProtocol"):
                valid = isinstance(parent, ast.ClassDef) and node in parent.bases
            elif (module, member) == ("websockets.frames", "CloseCode"):
                valid = id(node) in annotations or (
                    isinstance(parent, ast.Attribute)
                    and parent.attr in {"MESSAGE_TOO_BIG", "POLICY_VIOLATION"}
                    and isinstance(parent.ctx, ast.Load)
                )
            else:
                called = isinstance(parent, ast.Call) and parent.func is node
                valid = called or id(node) in annotations
            if not valid:
                violations.append(
                    Violation(
                        path, node.lineno, "network-outside-gateway", "ใช้ import ที่ยกเว้นนอกหน้าที่ที่อนุมัติ"
                    )
                )
        symbol = member_of(node)
        if isinstance(node, ast.Attribute) and symbol is not None:
            parent = parents.get(id(node))
            valid = symbol[1] == allowed[symbol[0]] and (
                (isinstance(parent, ast.Call) and parent.func is node)
                or (symbol == ("httpx", "AsyncClient") and id(node) in annotations)
            )
            if not valid:
                violations.append(
                    Violation(
                        path, node.lineno, "network-outside-gateway", "สมาชิกเครือข่ายนอกหน้าที่ที่อนุมัติ"
                    )
                )

    clients: set[str] = set()

    def is_client(node: ast.AST) -> bool:
        return (isinstance(node, ast.Name) and node.id in clients) or (
            isinstance(node, ast.Call) and member_of(node.func) == ("httpx", "AsyncClient")
        )

    functions = {
        node.name: node
        for node in nodes
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    approved_factories = {"live_wallet_factory", "live_candle_source"}
    if path.parts[-4:] == ("tiewtrade", "services", "market_data", "main.py"):
        approved_factories.add("live_price_feed")
    venue_factories = {
        alias.asname or alias.name
        for node in nodes
        if isinstance(node, ast.ImportFrom) and node.module == "tiewtrade.venues"
        for alias in node.names
        if alias.name in approved_factories
    }
    for node in nodes:
        if (
            isinstance(node, ast.arg)
            and node.annotation
            and member_of(node.annotation) == ("httpx", "AsyncClient")
        ):
            clients.add(node.arg)
    previous: set[str] | None = None
    while clients != previous:
        previous = clients.copy()
        for node in nodes:
            if isinstance(node, ast.Assign) and is_client(node.value):
                clients.update(target.id for target in node.targets if isinstance(target, ast.Name))
            elif (
                isinstance(node, ast.withitem)
                and is_client(node.context_expr)
                and isinstance(node.optional_vars, ast.Name)
            ):
                clients.add(node.optional_vars.id)
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in functions
            ):
                arguments = functions[node.func.id].args
                parameters = arguments.posonlyargs + arguments.args
                for parameter, argument in zip(parameters, node.args, strict=False):
                    if is_client(argument):
                        clients.add(parameter.arg)
                for keyword in node.keywords:
                    if keyword.arg and is_client(keyword.value):
                        clients.add(keyword.arg)
    for node in nodes:
        if isinstance(node, ast.Call) and member_of(node.func) == ("httpx", "AsyncClient"):
            parent = parents.get(id(node))
            bound_name = isinstance(parent, ast.Assign) and all(
                isinstance(target, ast.Name) for target in parent.targets
            )
            bound_context = isinstance(parent, ast.withitem) and isinstance(
                parent.optional_vars, ast.Name
            )
            if not bound_name and not bound_context:
                violations.append(
                    Violation(
                        path,
                        node.lineno,
                        "network-outside-gateway",
                        "client ต้องประกอบใน engine ไม่คืนออกจากโมดูล",
                    )
                )
        if isinstance(node, ast.Attribute) and is_client(node.value):
            violations.append(
                Violation(
                    path,
                    node.lineno,
                    "network-outside-gateway",
                    "client ที่สร้างเพื่อส่งเข้า venue ห้ามใช้งานเอง",
                )
            )
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in clients:
            parent = parents.get(id(node))
            if isinstance(parent, ast.keyword):
                parent = parents.get(id(parent))
            valid_alias = isinstance(parent, ast.Assign) and all(
                isinstance(target, ast.Name) for target in parent.targets
            )
            valid_call = (
                isinstance(parent, ast.Call)
                and isinstance(parent.func, ast.Name)
                and parent.func.id in (functions.keys() | venue_factories)
                and parent.func is not node
            )
            if valid_call and isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name):
                function = functions.get(parent.func.id)
                if function is not None:
                    valid_call = function.args.vararg is None and function.args.kwarg is None
            if not valid_alias and not valid_call:
                violations.append(
                    Violation(
                        path,
                        node.lineno,
                        "network-outside-gateway",
                        "client ต้องส่งเข้า venue โดยไม่ส่งต่อผ่านช่องทางอื่น",
                    )
                )
    return violations
