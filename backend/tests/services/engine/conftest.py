"""ของกลางของเทสต์ worker — กุญแจของงานนี้ ผู้ใช้จริง และตลาดปลอมที่ตอบได้ทุกแบบ"""

from __future__ import annotations

import base64
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.api_keys import store_key
from tiewtrade.infra.crypto import KEY_BYTES, KeyPurpose, KeySource
from tiewtrade.infra.db import user_session
from tiewtrade.infra.users import create_user
from tiewtrade.venues.errors import VenueError
from tiewtrade.venues.signing import RequestSigner
from tiewtrade.venues.wallets import WalletHoldings

TEST_VENUE_KEY = "1:" + base64.b64encode(b"V" * KEY_BYTES).decode("ascii")
PUBLIC = "PUBLICKEY000000ABCD"
SECRET = "secret-that-must-never-come-back"


@pytest.fixture(autouse=True)
def _venue_sealing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(KeyPurpose.VENUE_API_SECRET.environment_variable, TEST_VENUE_KEY)


@pytest.fixture
def venue_keys(_venue_sealing_key: None) -> KeySource:
    return KeySource.from_environment(KeyPurpose.VENUE_API_SECRET)


@dataclass
class ScriptedWallet:
    """ตลาดปลอมที่ตอบตามบทที่เทสต์เขียน — จดทุกครั้งที่ถูกเรียก

    **จดลายเซ็นที่ได้รับด้วย** เพื่อให้เทสต์พิสูจน์ได้ว่า worker เปิดผนึกถูกใบ
    """

    outcomes: list[VenueError | WalletHoldings]
    signers: list[RequestSigner] = field(default_factory=list)

    def factory(self) -> object:
        def build(signer: RequestSigner) -> ScriptedWallet:
            self.signers.append(signer)
            return self

        return build

    @property
    def calls(self) -> int:
        return len(self.signers)

    async def holdings(self) -> WalletHoldings:
        outcome = self.outcomes.pop(0) if self.outcomes else _empty_holdings()
        if isinstance(outcome, VenueError):
            raise outcome
        return outcome


def _empty_holdings() -> WalletHoldings:
    return WalletHoldings(received_at=datetime.now(UTC), holdings=())


async def as_structure_owner(
    migrator_engine: AsyncEngine, statement: str, parameters: dict[str, object] | None = None
) -> None:
    """สั่งคำสั่งหนึ่งโดยปลด `FORCE ROW LEVEL SECURITY` ชั่วคราว

    **ต้องปลดเพราะกลไกทำงานจริง** — `FORCE` ครอบเจ้าของตารางด้วย ฉะนั้นแม้แต่บทบาท
    ที่รัน migration ก็มองไม่เห็นแถวของผู้ใช้โดยไม่ระบุตัวตน · คำสั่งที่ไม่ปลดจะ
    **กระทบศูนย์แถวแบบเงียบ ๆ** ไม่ใช่ล้มเหลว ซึ่งทำให้เทสต์ผ่านด้วยเหตุผลที่ผิด
    (เจอมากับตัวตอนเขียนเทสต์ชุดนี้)

    ใช้เฉพาะในเทสต์ และใส่ `FORCE` คืนเสมอแม้คำสั่งจะล้มเหลว
    """
    async with migrator_engine.begin() as connection:
        await connection.execute(text("ALTER TABLE user_api_keys NO FORCE ROW LEVEL SECURITY"))
        try:
            await connection.execute(text(statement), parameters or {})
        finally:
            await connection.execute(text("ALTER TABLE user_api_keys FORCE ROW LEVEL SECURITY"))


@pytest_asyncio.fixture(autouse=True)
async def _only_this_tests_keys(migrator_engine: AsyncEngine) -> None:
    """ล้างตารางก่อนทุกเทสต์ของ worker

    รอบตรวจ **ข้าม RLS โดยเจตนา** เพราะมันต้องหางานของผู้ใช้ทุกคน ฉะนั้นแถวที่
    เทสต์ก่อนหน้าทิ้งไว้จะถูกนับรวมในสรุปของรอบนี้ แล้วเทสต์จะผ่านหรือแดงด้วยเหตุผล
    ที่ไม่ใช่สิ่งที่มันตรวจ — **ล้างสภาพ ไม่ใช่ปิดกลไก** (แบบแผนเดียวกับเทสต์ของ F-05)
    """
    await as_structure_owner(migrator_engine, "DELETE FROM user_api_keys")


@pytest.fixture
def market() -> Iterator[ScriptedWallet]:
    yield ScriptedWallet(outcomes=[])


@pytest_asyncio.fixture
async def key_of_a_user(api_engine: AsyncEngine, venue_keys: KeySource) -> tuple[UUID, UUID]:
    """ผู้ใช้หนึ่งคนที่เพิ่ง เพิ่ม key หนึ่งใบ — คืน (user_id, key_id)"""
    owner = uuid4()
    await create_user(api_engine, owner)
    async with user_session(api_engine, owner) as session:
        key_id = await store_key(
            session,
            venue_keys,
            user_id=owner,
            label="หลัก",
            key_public=PUBLIC,
            secret=SECRET,
        )
    return owner, key_id
