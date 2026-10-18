"""Shared account-use value without credential or persistence dependencies."""

from enum import StrEnum


class AccountUse(StrEnum):
    MANUAL = "MANUAL"
    BOT = "BOT"
