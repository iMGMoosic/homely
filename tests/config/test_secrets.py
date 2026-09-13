from pathlib import Path

from pydantic import BaseModel, SecretStr

from homely.config.secrets import REDACTED, SecretStore, secret_field_names


class S(BaseModel):
    name: str = "x"
    api_key: SecretStr | None = None
    token: SecretStr = SecretStr("")


def test_field_detection():
    assert secret_field_names(S) == {"api_key", "token"}


def test_extract_merge_redact(tmp_path: Path):
    store = SecretStore(tmp_path / "secrets.yaml")
    model = S(name="n", api_key=SecretStr("k1"), token=SecretStr("t1"))
    public = store.extract("inst", S, model)
    assert "api_key" not in public and public["name"] == "n"
    store.save()
    assert oct((tmp_path / "secrets.yaml").stat().st_mode)[-3:] == "600"

    redacted = store.redact("inst", S, public)
    assert redacted["api_key"] == REDACTED

    # Blank or redacted incoming keeps the stored value; explicit None clears.
    merged = store.merge("inst", S, {"name": "n", "api_key": REDACTED, "token": ""})
    assert merged["api_key"] == "k1" and merged["token"] == "t1"
    merged = store.merge("inst", S, {"name": "n", "api_key": None})
    assert merged["api_key"] is None

    store2 = SecretStore(tmp_path / "secrets.yaml")
    assert store2.get("inst", "api_key") == "k1"
