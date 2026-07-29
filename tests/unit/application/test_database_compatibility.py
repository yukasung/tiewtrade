from tiewtrade.application.database_compatibility import DatabaseCompatibilityError


def test_database_compatibility_error_is_an_application_contract() -> None:
    assert isinstance(DatabaseCompatibilityError(), RuntimeError)
