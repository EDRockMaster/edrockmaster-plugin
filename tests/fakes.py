"""Test doubles shared by several test modules."""


class FakeConfig:
    """Stands for EDMC's ``config``.

    Stricter than EDMC 6.1, whose getters never raise: a type mismatch raises
    ``ValueError`` here, as older config back-ends did, so that both behaviours
    are covered.
    """

    def __init__(self, values: dict[str, object] | None = None) -> None:
        self.values: dict[str, object] = dict(values or {})

    def get_str(self, key: str, *, default: str | None = None) -> str | None:
        value = self.values.get(key, default)
        if value is not None and not isinstance(value, str):
            raise ValueError(key)
        return value

    def get_bool(self, key: str, *, default: bool | None = None) -> bool:
        value = self.values.get(key, default)
        if not isinstance(value, bool):
            raise ValueError(key)
        return value

    def set(self, key: str, value: str | bool) -> None:
        self.values[key] = value
