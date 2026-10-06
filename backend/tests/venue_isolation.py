"""ตัวตรวจว่าชั้นแยก venue ยังแยกจริง (F-33 RQ-12, RQ-14)

สองด่านที่ import-linter ทำแทนไม่ได้:

1. **คำศัพท์ของตลาดรั่วออกนอก `venues`** — การรั่วแบบนี้ไม่ใช่การ import
   แต่เป็นข้อความหรือชื่อที่เขียนไว้ในโค้ด
2. **ส่วนกลางของ `venues` รู้จักเครือข่าย** — ตรวจด้วยรายการที่อนุญาต ไม่ใช่รายการที่ห้าม
   เพราะรายการที่ห้ามต้องตามเติมชื่อทุกครั้งที่เพิ่ม dependency แล้วจะลืม
   (บทเรียนเดียวกับตัวตรวจความบริสุทธิ์ของ `core`)

**อ่านโครงสร้างโค้ด ไม่ค้นข้อความทั้งไฟล์** และ **ข้าม docstring** เพราะ docstring
อ้างถึงสเปกและชื่อตลาดเป็นเรื่องปกติและจำเป็น — การจับ docstring จะทำให้ต้องเลี่ยงคำ
ในเอกสารซึ่งทำให้เอกสารแย่ลงโดยไม่ได้ปลอดภัยขึ้น (บทเรียนจากตัวตรวจของ F-01)

**คำศัพท์ที่ห้ามมาจากตัวเชื่อมเอง ไม่ใช่รายการที่เขียนไว้ที่นี่** แต่ละ package ตัวเชื่อม
ประกาศ `VENUE_VOCABULARY` ของตัวเอง ด่านอ่านด้วย AST แล้วรวมเป็นรายการที่ห้าม
การเพิ่มตลาดใหม่จึงขยายด่านให้เองโดยไม่ต้องมีใครจำ (F-35 plan.md ข้อ 7.2)

**ขอบเขตของด่านเครือข่าย: เฉพาะส่วนกลาง ไม่ครอบ package ของตัวเชื่อมจริง**
`architecture.md` หัวข้อ 1 วางตัวเชื่อมไว้ข้างใน `venues` และตัวเชื่อมต้องต่อเครือข่าย
เป็นงานหลัก ถ้าด่านครอบทั้ง package จะบล็อก F-35 ตั้งแต่บรรทัดแรก
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.purity import Violation

#: ชื่อที่ package ตัวเชื่อมแต่ละตัวต้องใช้ประกาศคำศัพท์ของตลาดตัวเอง
VOCABULARY_DECLARATION = "VENUE_VOCABULARY"

#: ชื่อคู่เทรดแบบที่ตลาดเขียนติดกันเป็นคำเดียว เช่น `BTCUSDT`
#: ชั้นกลางใช้ `Symbol` ที่แยกสองส่วน จึงไม่มีเหตุผลให้รูปแบบนี้อยู่ในโค้ด
JOINED_PAIR = re.compile(r"^[A-Z]{2,6}(USDT|USDC|BUSD|THB|BTC|ETH)$")

#: ไลบรารีที่ส่วนกลางของ `venues` ใช้ได้ — รายการที่อนุญาต
ALLOWED_IMPORTS: frozenset[str] = frozenset(
    {
        "__future__",
        "collections",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "functools",
        "re",
        "typing",
        "tiewtrade",
    }
)


def adapter_packages(venues_root: Path) -> tuple[Path, ...]:
    """package ของตัวเชื่อมแต่ละตลาด — โฟลเดอร์ย่อยของ `venues/` ที่เป็น package"""
    return tuple(sorted(path.parent for path in venues_root.glob("*/__init__.py")))


def declared_venue_words(venues_root: Path) -> tuple[frozenset[str], list[Violation]]:
    """คำศัพท์ของตลาดที่ **ตัวเชื่อมประกาศเอง** รวมจากทุก package (F-35 plan.md ข้อ 7.2)

    อ่านด้วย AST ไม่ `import` เพราะด่านต้องอ่านโค้ดได้โดยไม่ต้องรันโค้ดนั้น

    **ตัวเชื่อมที่ไม่ประกาศคำศัพท์เลยถือว่าผิด** ตัวเชื่อมพาชื่อตลาดเข้ามาเป็นงานหลัก
    ถ้าไม่มีคำของตัวเองแปลว่ามีคนลืม แล้วด่านจะเงียบลงทีละตลาดโดยไม่มีอะไรเตือน
    """
    words: set[str] = set()
    violations: list[Violation] = []
    for package in adapter_packages(venues_root):
        init = package / "__init__.py"
        declared = _declared_vocabulary(init)
        if not declared:
            violations.append(
                Violation(
                    init,
                    0,
                    "missing-vocabulary",
                    f"package ตัวเชื่อมต้องประกาศ {VOCABULARY_DECLARATION} ที่ไม่ว่าง",
                )
            )
            continue
        words.update(declared)
    return frozenset(words), violations


def _declared_vocabulary(init: Path) -> frozenset[str]:
    """ค่าของ `VENUE_VOCABULARY` ในไฟล์หนึ่ง — ว่างเปล่าถ้าไม่มีหรืออ่านไม่ได้"""
    tree = ast.parse(init.read_text(encoding="utf-8"), filename=str(init))
    for node in ast.walk(tree):
        target = _assigned_name(node)
        if target != VOCABULARY_DECLARATION or not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if value is None:
            continue
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "frozenset"
            and len(value.args) == 1
        ):
            value = value.args[0]
        try:
            literal = ast.literal_eval(value)
        except ValueError:
            return frozenset()
        if isinstance(literal, (set, frozenset, tuple, list)) and all(
            isinstance(word, str) and word for word in literal
        ):
            return frozenset(word.lower() for word in literal)
    return frozenset()


def _assigned_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.AnnAssign):
        return _identifier(node.target) or None
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        return _identifier(node.targets[0]) or None
    return None


def central_venue_modules(venues_root: Path) -> tuple[Path, ...]:
    """ไฟล์ของ **ส่วนกลาง** ของชั้น venue

    "ไฟล์ `.py` ที่อยู่ระดับบนสุดของ `venues/`" คือกฎของขอบเขตนี้ ไม่ใช่รายชื่อที่จำไว้
    — `glob` ที่ไม่ลงลึกจึงเป็นตัวกฎเอง package ของตัวเชื่อมจริงอยู่ในโฟลเดอร์ย่อย
    จึงถูกกันออกโดยโครงสร้าง ไม่ใช่โดยการที่ใครสักคนจำได้ว่าต้องไม่ใส่ชื่อมันลงรายการ
    """
    return tuple(sorted(venues_root.glob("*.py")))


#: ไลบรารีที่แตะเครือข่ายได้ — **รายการที่ห้าม** ไม่ใช่รายการที่อนุญาต
#:
#: ต่างจากด่านของส่วนกลางโดยเจตนา: ที่นั่นถามว่า "ไฟล์นี้บริสุทธิ์ไหม" จึงต้องใช้
#: รายการที่อนุญาต ส่วนที่นี่ถามว่า "เครือข่ายอยู่ไฟล์เดียวไหม" ตัวเชื่อมใช้ของใน
#: standard library ได้ตามต้องการ การใช้รายการที่อนุญาตที่นี่จะกลายเป็นรายการ
#: ที่ต้องตามเติมทุกครั้งที่ตัวเชื่อมใช้ของใหม่ และทิศทางอ้อมถูก import-linter คุมไว้แล้ว
NETWORK_LIBRARIES: frozenset[str] = frozenset(
    {"httpx", "socket", "urllib", "requests", "aiohttp", "websockets", "http", "ssl"}
)

# asyncio ยังใช้จัดคิวงานได้ · บล็อกเฉพาะสมาชิกที่แตะเครือข่าย
_ASYNCIO_NETWORK = frozenset(
    {
        "open_connection",
        "start_server",
        "open_unix_connection",
        "start_unix_server",
        "create_connection",
        "create_server",
        "create_unix_connection",
        "create_unix_server",
        "create_datagram_endpoint",
        "connect_accepted_socket",
        "start_tls",
        "getaddrinfo",
        "getnameinfo",
        "sock_connect",
        "sock_accept",
        "sock_recv",
        "sock_recv_into",
        "sock_recvfrom",
        "sock_recvfrom_into",
        "sock_sendall",
        "sock_sendto",
        "sendfile",
        "sock_sendfile",
    }
)
_ASYNCIO_FACTORIES = {
    "get_running_loop": "loop",
    "get_event_loop": "loop",
    "new_event_loop": "loop",
    "AbstractEventLoop": "loop",
    "BaseEventLoop": "loop",
    "SelectorEventLoop": "loop",
    "ProactorEventLoop": "loop",
    "Runner": "runner",
    "get_event_loop_policy": "policy",
    "AbstractEventLoopPolicy": "policy",
    "DefaultEventLoopPolicy": "policy",
    "WindowsSelectorEventLoopPolicy": "policy",
    "WindowsProactorEventLoopPolicy": "policy",
}
_ASYNCIO_METHOD_FACTORIES = {
    ("runner", "get_loop"): "loop",
    ("policy", "get_event_loop"): "loop",
    ("policy", "new_event_loop"): "loop",
}


def _expression_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and (parent := _expression_name(node.value)):
        return f"{parent}.{node.attr}"
    return None


def _own_returns(node: ast.AST) -> list[ast.Return]:
    """ไม่รวม return ของฟังก์ชัน/คลาสซ้อนซึ่งไม่ใช่ผลของผู้เรียกนี้."""
    found: list[ast.Return] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(child, ast.Return):
            found.append(child)
        else:
            found.extend(_own_returns(child))
    return found


def check_asyncio_network(path: Path) -> list[Violation]:
    """สมาชิก network ของ asyncio รวม aliases/loop objects · ไม่ execute source."""
    nodes = code_nodes(path)
    # แต่ละชื่อเป็นของ lexical scope; local ที่ยังไม่รู้ชนิดก็บังชื่อชั้นนอก
    scopes: dict[ast.AST, ast.AST] = {}
    parents: dict[ast.AST, ast.AST | None] = {nodes[0]: None}
    locals_of: dict[ast.AST, set[str]] = {nodes[0]: set()}

    def index_scope(node: ast.AST, scope: ast.AST) -> None:
        scopes[node] = scope
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            locals_of[scope].add(node.name)
            parents[node] = scope
            locals_of[node] = set()
            for child in ast.iter_child_nodes(node):
                index_scope(
                    child,
                    node if child in node.body or child is getattr(node, "args", None) else scope,
                )
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            parents[node] = scope
            locals_of[node] = set()
            for index, generator in enumerate(node.generators):
                scopes[generator] = node
                index_scope(generator.target, node)
                # Python ประเมิน iterable แรกก่อนเข้า comprehension scope
                index_scope(generator.iter, scope if index == 0 else node)
                for condition in generator.ifs:
                    index_scope(condition, node)
            results = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
            for result in results:
                index_scope(result, node)
            return
        if isinstance(node, ast.Lambda):
            parents[node] = scope
            locals_of[node] = set()
            index_scope(node.args, node)
            index_scope(node.body, node)
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            locals_of[scope].add(node.id)
        elif isinstance(node, ast.arg):
            locals_of[scope].add(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                locals_of[scope].add(alias.asname or alias.name.split(".")[0])
        for child in ast.iter_child_nodes(node):
            # annotations/defaults ใช้ชื่อใน enclosing scope ของ signature
            signature_value = isinstance(node, ast.arg) or (
                isinstance(node, ast.arguments)
                and (child in node.defaults or child in node.kw_defaults)
            )
            index_scope(child, (parents[scope] or scope) if signature_value else scope)

    index_scope(nodes[0], nodes[0])
    globals_of: dict[ast.AST, set[str]] = {}
    for node in nodes:
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            scope = scopes[node]
            locals_of[scope].difference_update(node.names)
            if isinstance(node, ast.Global):
                globals_of.setdefault(scope, set()).update(node.names)

    def binding(node: ast.AST, name: str) -> tuple[ast.AST, str]:
        scope = scopes[node]
        root = name.split(".")[0]
        while root not in locals_of[scope] and (parent := parents[scope]) is not None:
            if root in globals_of.get(scope, set()):
                return nodes[0], name
            # method/closure ไม่ค้นชื่อใน class namespace แบบตัวแปร local
            if isinstance(
                scope,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.Lambda,
                    ast.ListComp,
                    ast.SetComp,
                    ast.DictComp,
                    ast.GeneratorExp,
                ),
            ):
                while isinstance(parent, ast.ClassDef):
                    parent = parents[parent]
                    if parent is None:
                        break
            if parent is None:
                break
            scope = parent
        # self/cls fields เป็นของ class เดียวกันแม้เขียน/อ่านคนละ method
        if "." in name and isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = parents[scope]
            parameters = scope.args.posonlyargs + scope.args.args
            decorators = {_expression_name(item) for item in scope.decorator_list}
            if (
                isinstance(owner, ast.ClassDef)
                and parameters
                and root == parameters[0].arg
                and "staticmethod" not in decorators
            ):
                receiver = "class" if "classmethod" in decorators else "instance"
                return owner, f"{receiver}.{name.split('.', 1)[1]}"
        return scope, name

    classes = {binding(node, node.name): node for node in nodes if isinstance(node, ast.ClassDef)}
    constructor_fields = set()
    for node in nodes:
        if isinstance(node, ast.Assign) or (
            isinstance(node, ast.AnnAssign) and node.value is not None
        ):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                scope = scopes[node]
                if (
                    isinstance(target, ast.Attribute)
                    and (name := _expression_name(target))
                    and isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and scope.name == "__init__"
                    and node in scope.body
                ):
                    constructor_fields.add(binding(target, name))

    def class_order(
        owner: ast.ClassDef, active: frozenset[ast.AST] = frozenset()
    ) -> tuple[ast.ClassDef, ...]:
        """C3 order ของ base ที่ประกาศในไฟล์ · ไม่ import/execute source."""
        if owner in active:
            return ()
        bases = [
            base
            for expression in owner.bases
            if (name := _expression_name(expression))
            and (base := classes.get(binding(expression, name))) is not None
        ]
        sequences = [list(class_order(base, active | {owner})) for base in bases] + [list(bases)]
        result = [owner]
        while remaining := [sequence for sequence in sequences if sequence]:
            head = next(
                (
                    sequence[0]
                    for sequence in remaining
                    if all(sequence[0] not in other[1:] for other in remaining)
                ),
                None,
            )
            if head is None:
                return (owner,)  # cyclic/inconsistent bases ไม่มี MRO ที่เชื่อถือได้
            result.append(head)
            for sequence in remaining:
                if sequence[0] is head:
                    sequence.pop(0)
        return tuple(result)

    def field_binding(node: ast.AST, name: str) -> tuple[ast.AST, str]:
        owner, field = binding(node, name)
        if isinstance(owner, ast.ClassDef) and field.startswith(("instance.", "class.")):
            candidate: tuple[ast.AST, str] | None = None
            for ancestor in class_order(owner):
                key = ancestor, field
                # optional setter ยังไม่ลบความเป็นไปได้ของ inherited loop
                if objects.get(key) == "loop":
                    return key
                if candidate is None and (key in objects or key in symbols):
                    candidate = key
                # เฉพาะ assignment ตรงใน constructor จึงบัง ancestor evidence
                if key in constructor_fields:
                    return candidate or key
            return candidate or (owner, field)
        return owner, field

    symbols: dict[tuple[ast.AST, str], tuple[str, ...]] = {}
    objects: dict[tuple[ast.AST, str], str] = {}
    returns: dict[tuple[ast.AST, str], str] = {}
    hits: dict[int, str] = {}
    functions = {
        binding(node, node.name): node
        for node in nodes
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "asyncio":
                    symbols[binding(node, alias.asname or "asyncio")] = (
                        tuple(alias.name.split(".")) if alias.asname else ("asyncio",)
                    )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module
            and node.module.split(".")[0] == "asyncio"
        ):
            for alias in node.names:
                symbols[binding(node, alias.asname or alias.name)] = (
                    *node.module.split("."),
                    alias.name,
                )
                if alias.name in _ASYNCIO_NETWORK or alias.name == "*":
                    hits[node.lineno] = alias.name

    def qualified(node: ast.AST) -> tuple[str, ...] | None:
        name = _expression_name(node)
        if name is not None and (key := field_binding(node, name)) in symbols:
            return symbols[key]
        if isinstance(node, ast.Attribute) and (parent := qualified(node.value)):
            return (*parent, node.attr)
        return None

    def kind(node: ast.AST | None) -> str | None:
        if isinstance(node, ast.Await):
            return kind(node.value)
        if isinstance(node, (ast.BoolOp, ast.IfExp)):
            choices = node.values if isinstance(node, ast.BoolOp) else [node.body, node.orelse]
            resources = [kind(choice) for choice in choices]
            # ผลลัพธ์อาจเป็น loop จากฝั่งใดก็ได้ จึงต้องตรวจ network แบบ conservative
            if "loop" in resources:
                return "loop"
            return next((resource for resource in resources if resource is not None), None)
        if isinstance(node, ast.Call):
            return call_result(node.func)
        return (
            objects.get(field_binding(node, _expression_name(node) or ""))
            if node is not None
            else None
        )

    def call_result(function: ast.AST) -> str | None:
        symbol = qualified(function)
        if symbol and symbol[0] == "asyncio":
            return _ASYNCIO_FACTORIES.get(symbol[-1])
        if isinstance(function, ast.Attribute) and (owner := kind(function.value)):
            return _ASYNCIO_METHOD_FACTORIES.get((owner, function.attr))
        if isinstance(function, ast.Name):
            return returns.get(binding(function, function.id))
        return None

    def annotation_kind(annotation: ast.AST) -> str | None:
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            try:
                parsed = ast.parse(annotation.value, mode="eval").body
                for item in ast.walk(parsed):
                    scopes[item] = scopes[annotation]
                annotation = parsed
            except SyntaxError:
                return None
        for item in ast.walk(annotation):
            symbol = qualified(item)
            if symbol and symbol[0] == "asyncio" and symbol[-1][:1].isupper():
                resource = _ASYNCIO_FACTORIES.get(symbol[-1])
                if resource:
                    return resource
        return None

    # เพิ่ม binding เท่านั้น จึงจบแน่นอน แม้ source มี aliases วนกลับหากัน
    previous: tuple[int, int, int] | None = None
    while previous != (len(symbols), len(objects), len(returns)):
        previous = (len(symbols), len(objects), len(returns))
        for node in nodes:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                symbol = qualified(node.value) if node.value is not None else None
                resource = kind(node.value)
                result = call_result(node.value) if node.value is not None else None
                if isinstance(node, ast.AnnAssign):
                    resource = resource or annotation_kind(node.annotation)
                for target in targets:
                    if name := _expression_name(target):
                        if symbol:
                            symbols.setdefault(binding(target, name), symbol)
                        if resource:
                            objects.setdefault(binding(target, name), resource)
                        if result:
                            returns.setdefault(binding(target, name), result)
            elif isinstance(node, ast.arg) and node.annotation:
                if resource := annotation_kind(node.annotation):
                    objects.setdefault(binding(node, node.arg), resource)
            elif isinstance(node, ast.withitem) and node.optional_vars:
                name, resource = _expression_name(node.optional_vars), kind(node.context_expr)
                if name and resource:
                    objects.setdefault(binding(node.optional_vars, name), resource)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for returned in _own_returns(node):
                    if resource := kind(returned.value):
                        returns.setdefault(binding(node, node.name), resource)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                function = functions.get(binding(node.func, node.func.id))
                if function:
                    args = function.args
                    for parameter, argument in zip(
                        args.posonlyargs + args.args, node.args, strict=False
                    ):
                        if resource := kind(argument):
                            objects.setdefault((function, parameter.arg), resource)
                    parameter_names = {
                        parameter.arg
                        for parameter in args.posonlyargs + args.args + args.kwonlyargs
                    }
                    for keyword in node.keywords:
                        if keyword.arg in parameter_names and (resource := kind(keyword.value)):
                            objects.setdefault((function, keyword.arg), resource)

    for node in nodes:
        symbol = qualified(node)
        if (
            isinstance(node, (ast.Name, ast.Attribute))
            and symbol
            and symbol[0] == "asyncio"
            and symbol[-1] in _ASYNCIO_NETWORK
        ):
            hits[node.lineno] = symbol[-1]
        elif (
            isinstance(node, ast.Attribute)
            and kind(node.value) == "loop"
            and node.attr in _ASYNCIO_NETWORK
        ):
            hits[node.lineno] = node.attr
    return [
        Violation(path, line, "network-outside-gateway", f"asyncio.{member} นอก gateway")
        for line, member in sorted(hits.items())
    ]


def check_network_only_in(package_root: Path, gateway: str) -> list[Violation]:
    """ยืนยันว่ามีไฟล์เดียวใน package ที่รู้จักเครือข่าย (F-35 V-3)

    ตรวจ **ทุกไฟล์ของ package รวมโฟลเดอร์ย่อย** เพราะกฎคือ "ทางเดียวที่ออกไปข้างนอก"
    ถ้ามีสองทาง การจองโควตาก่อนเรียกจะเลี่ยงได้โดยไม่มีอะไรเตือน
    """
    violations: list[Violation] = []
    for path in sorted(package_root.rglob("*.py")):
        if path == package_root / f"{gateway}.py":
            continue
        violations.extend(check_asyncio_network(path))
        for module, node in network_imports(path):
            _reject_network(path, module, node.lineno, violations)
    return violations


def network_imports(path: Path) -> tuple[tuple[str, ast.Import | ast.ImportFrom], ...]:
    """อ่าน import เครือข่ายให้ด่าน venue และด่านทั่ว src ใช้กฎชุดเดียวกัน"""
    found: list[tuple[str, ast.Import | ast.ImportFrom]] = []
    for node in code_nodes(path):
        if isinstance(node, ast.Import):
            found.extend(
                (alias.name, node)
                for alias in node.names
                if alias.name.split(".")[0] in NETWORK_LIBRARIES
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.split(".")[0] in NETWORK_LIBRARIES
        ):
            found.append((node.module, node))
    return tuple(found)


def _reject_network(path: Path, module: str, line: int, violations: list[Violation]) -> None:
    if module.split(".")[0] in NETWORK_LIBRARIES:
        violations.append(
            Violation(path, line, "network-outside-gateway", f"{module!r} อยู่นอกไฟล์ทางออกเดียว")
        )


def modules_not_reaching(package_root: Path, gateway: str) -> tuple[Path, ...]:
    """ไฟล์ระดับบนสุดของ package ที่ **ไม่ได้** ผ่านโมดูลหนึ่ง (F-35 plan.md ข้อ 7.1)

    ใช้หาว่าโมดูลไหนของตัวเชื่อมต้องไม่รู้จักเครือข่ายเลย: ทุกไฟล์ที่ไม่ใช่
    `gateway` เองและไม่ `import` มัน `__init__.py` ไม่นับเพราะหน้าที่ของมันคือ
    ประกอบของทุกชิ้นมารวมกัน จึงต้องถึงเครือข่ายโดยปริยาย

    กฎนี้เป็นตัวกฎเอง ไม่ใช่รายชื่อที่จำไว้ — เพิ่มโมดูลใหม่ที่ไม่ผ่าน `gateway`
    แล้วลืมเติมใน contract ของ import-linter เทสต์จะแดงทันที
    """
    found: list[Path] = []
    for path in sorted(package_root.glob("*.py")):
        if path.name in ("__init__.py", f"{gateway}.py"):
            continue
        if not _imports_sibling(path, gateway):
            found.append(path)
    return tuple(found)


def _imports_sibling(path: Path, module: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.split(".")[-1] == module:
                return True
        elif isinstance(node, ast.Import) and any(
            alias.name.split(".")[-1] == module for alias in node.names
        ):
            return True
    return False


def _venue_words_in(text: str, words: frozenset[str]) -> list[str]:
    """คำของตลาดที่พบในข้อความหนึ่ง"""
    return re.findall("|".join(sorted(re.escape(word) for word in words)), text.lower())


def check_vocabulary(
    path: Path,
    words: frozenset[str],
    *,
    allowed_literals: frozenset[tuple[int, int]] = frozenset(),
) -> list[Violation]:
    """หาคำศัพท์ของตลาดในไฟล์หนึ่ง — ใช้กับไฟล์นอก `venues`

    เดินต้นไม้รอบเดียว โดยจำ docstring ที่เจอระหว่างทางไว้ข้าม

    `words` มาจาก `declared_venue_words` ไม่ใช่รายการที่เขียนไว้ในไฟล์นี้
    เพราะคำของตลาดเป็นของตัวเชื่อม ไม่ใช่ของด่าน
    """
    if not words:
        raise ValueError("ด่านคำศัพท์ที่ไม่มีคำให้หาคือด่านที่เขียวตลอด")
    violations: list[Violation] = []

    for node in code_nodes(path):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            # ชื่อคลาสและชื่อฟังก์ชันก็เป็นที่ที่คำศัพท์ของตลาดโผล่ได้
            # เช่น `def binance_price()` ซึ่งไม่ใช่ทั้งข้อความและไม่ใช่การอ้างชื่อ
            if not isinstance(node, ast.Module):
                violations.extend(_name_violations(path, node.name, node.lineno, words))
            continue

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if (node.lineno, node.col_offset) in allowed_literals:
                continue
            for word in _venue_words_in(node.value, words):
                violations.append(
                    Violation(path, node.lineno, "venue-word", f"ข้อความมีคำว่า {word!r}")
                )
            if JOINED_PAIR.match(node.value):
                violations.append(
                    Violation(
                        path,
                        node.lineno,
                        "joined-pair",
                        f"{node.value!r} เป็นชื่อคู่เทรดแบบของตลาด ใช้ Symbol แทน",
                    )
                )
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            # `from binance import Client` — ชื่อ module อยู่ที่นี่ ไม่ได้อยู่ใน alias
            violations.extend(_name_violations(path, node.module, node.lineno, words))
        elif isinstance(node, (ast.Name, ast.Attribute, ast.alias)):
            violations.extend(
                _name_violations(path, _identifier(node), getattr(node, "lineno", 0), words)
            )

    return violations


def _name_violations(path: Path, name: str, line: int, words: frozenset[str]) -> list[Violation]:
    """คำศัพท์ของตลาดที่ซ่อนอยู่ในชื่อหนึ่งชื่อ

    ตรวจทั้งคำของตลาดและชื่อคู่เทรดแบบติดกัน เพราะ `BTCUSDT = 1` เป็นชื่อตัวแปร
    ไม่ใช่ข้อความ จึงไม่ถูกจับโดยการตรวจค่าคงที่
    """
    found = [
        Violation(path, line, "venue-word", f"ชื่อ {name!r} มีคำว่า {word!r}")
        for word in _venue_words_in(name, words)
    ]
    if JOINED_PAIR.match(name):
        found.append(Violation(path, line, "joined-pair", f"ชื่อ {name!r} เป็นคู่เทรดแบบของตลาด"))
    return found


def code_nodes(path: Path) -> tuple[ast.AST, ...]:
    """โหนดที่ใช้จริง ไม่รวมข้อความ docstring — ใช้ร่วมกันทุกด่าน AST"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    nodes = tuple(ast.walk(tree))
    docstrings = {
        id(_docstring_constant(node))
        for node in nodes
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return tuple(node for node in nodes if id(node) not in docstrings)


def code_strings(path: Path) -> list[str]:
    """ข้อความที่โค้ดใช้จริงในไฟล์หนึ่ง — **ไม่รวม docstring**

    อยู่ที่นี่เพราะมีสามที่ที่ต้องถามคำถามเดียวกัน: ด่านคำศัพท์, เทสต์ที่ยืนยันว่า
    ตัวเชื่อมไม่มีทางสำรองของราคา และเทสต์ที่ยืนยันว่าสคริปต์เรียกแต่ endpoint
    ที่อนุมัติ — และทุกที่ต้องข้าม docstring เหมือนกัน เพราะเอกสารพูดถึงสิ่งที่
    **ไม่ทำ** เป็นเรื่องปกติและจำเป็น
    """
    return [
        node.value
        for node in code_nodes(path)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def identifiers(path: Path) -> set[str]:
    """ชื่อทุกชื่อที่โค้ดในไฟล์นั้นอ้างถึง — ไม่รวมข้อความและ docstring

    ใช้ถามว่า "โค้ดนี้ใช้ของชิ้นนั้นจริงไหม" ซึ่งต่างจากการค้นข้อความทั้งไฟล์
    ที่จะเจอชื่อในเอกสารที่อธิบายว่าทำไม **ไม่** ใช้ของชิ้นนั้น
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute, ast.alias)):
            found.update(_identifier(node).split("."))
    return found - {""}


def _docstring_constant(node: ast.AST) -> ast.Constant | None:
    """โหนดข้อความที่เป็น docstring ของโหนดนี้ ถ้ามี"""
    body = getattr(node, "body", [])
    if not body:
        return None
    first = body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return first.value
    return None


def _identifier(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.alias):
        return node.name
    return ""


def check_no_network(path: Path) -> list[Violation]:
    """ยืนยันว่าไฟล์นี้ import เฉพาะสิ่งที่อยู่ในรายการที่อนุญาต"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_module(alias.name, node.lineno, path, violations)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            _check_module(node.module, node.lineno, path, violations)

    return violations


def _check_module(module: str, line: int, path: Path, violations: list[Violation]) -> None:
    root = module.split(".")[0]
    if root not in ALLOWED_IMPORTS:
        violations.append(
            Violation(path, line, "not-allowed-import", f"{module!r} ไม่อยู่ในรายการที่อนุญาต")
        )
