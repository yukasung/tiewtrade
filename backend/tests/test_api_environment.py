"""The API test fixture must preserve the CI/disposable Redis target."""

import os
from inspect import unwrap

import pytest

from tests.api import conftest as api_fixtures


@pytest.mark.parametrize(
    "api_url,test_url,expected",
    [
        ("redis://127.0.0.1:6379/0", "redis://127.0.0.1:56379/0", "redis://127.0.0.1:6379/0"),
        ("redis://127.0.0.1:6381/4", None, "redis://127.0.0.1:6381/4"),
        (None, "redis://127.0.0.1:6379/0", "redis://127.0.0.1:6379/0"),
        (None, "redis://127.0.0.1:6382/2", "redis://127.0.0.1:6382/2"),
        (None, None, "redis://127.0.0.1:56379/0"),
        ("", "redis://127.0.0.1:6379/0", ""),
    ],
)
def test_api_fixture_preserves_redis_configuration(
    monkeypatch: pytest.MonkeyPatch,
    api_url: str | None,
    test_url: str | None,
    expected: str,
) -> None:
    for key, value in (
        ("TIEWTRADE_REDIS_URL_API", api_url),
        ("TIEWTRADE_TEST_REDIS_URL", test_url),
    ):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    # Exercise the actual fixture body without entering its database-dependent scope.
    unwrap(api_fixtures._api_environment)(monkeypatch)
    assert os.environ["TIEWTRADE_REDIS_URL_API"] == expected
