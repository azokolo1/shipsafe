import pytest

from shipsafe.config import Settings
from shipsafe.db import connect_kwargs, password_provider


def settings(**overrides) -> Settings:
    base = dict(
        service_name="shipsafe-test",
        version="test-sha",
        queue_backend="memory",
        queue_url=None,
        log_level="INFO",
        db_backend="postgres",
        db_host="db.example.internal",
    )
    base.update(overrides)
    return Settings(**base)


class FakeRds:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate_db_auth_token(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return f"token-{len(self.calls)}"


def test_iam_auth_generates_a_fresh_token_per_connection():
    rds = FakeRds()
    provider = password_provider(settings(), rds_client=rds)
    assert provider() == "token-1"
    assert provider() == "token-2"
    assert rds.calls[0] == {
        "DBHostname": "db.example.internal",
        "Port": 5432,
        "DBUsername": "shipsafe_app",
        "Region": "eu-west-2",
    }


def test_password_auth_requires_a_password():
    with pytest.raises(ValueError, match="DB_PASSWORD"):
        password_provider(settings(db_auth="password"))


def test_unknown_auth_mode_is_rejected():
    with pytest.raises(ValueError, match="DB_AUTH"):
        password_provider(settings(db_auth="none"))


def test_tls_is_verified_by_default():
    kwargs = connect_kwargs(settings(db_sslrootcert="/app/certs/rds-ca-bundle.pem"))
    assert kwargs["sslmode"] == "verify-full"
    assert kwargs["sslrootcert"] == "/app/certs/rds-ca-bundle.pem"
    assert "password" not in kwargs


def test_host_is_required():
    with pytest.raises(ValueError, match="DB_HOST"):
        connect_kwargs(settings(db_host=None))
