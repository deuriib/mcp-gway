"""Unit tests for domain-level ``{env:NAME}`` expansion."""

from __future__ import annotations

import pytest

from mcp_gway.domain.policy import expand_env_references


def test_expands_whole_value_placeholder() -> None:
    env = {"API_KEY": "{env:PROVIDER_API_KEY}"}
    lookup = {"PROVIDER_API_KEY": "synthetic-value-123"}.get

    result = expand_env_references(env, lookup)

    assert result == {"API_KEY": "synthetic-value-123"}


@pytest.mark.parametrize("name", ["_FOO1", "A", "a_b_9"])
def test_accepts_valid_name_charset(name: str) -> None:
    result = expand_env_references({"K": f"{{env:{name}}}"}, {name: "hit"}.get)

    assert result == {"K": "hit"}


@pytest.mark.parametrize(
    "value",
    ["plain", "", "prefix-{env:FOO}-suffix"],
)
def test_non_placeholder_values_pass_through(value: str) -> None:
    env = {"K": value}

    result = expand_env_references(env, {}.get)

    assert result == {"K": value}
    assert result is not env


def test_none_returns_none() -> None:
    assert expand_env_references(None, {}.get) is None


def test_empty_dict_returns_new_mapping() -> None:
    env: dict[str, str] = {}

    result = expand_env_references(env, {}.get)

    assert result == {}
    assert result is not env


def test_input_mapping_is_not_mutated() -> None:
    env = {"API_KEY": "{env:PROVIDER_API_KEY}"}

    result = expand_env_references(env, {"PROVIDER_API_KEY": "synthetic-value-123"}.get)

    assert result is not env
    assert env["API_KEY"] == "{env:PROVIDER_API_KEY}"


def test_missing_variable_raises_naming_variable() -> None:
    with pytest.raises(ValueError, match=r"\[reason=missing_env_ref\]") as excinfo:
        expand_env_references({"API_KEY": "{env:PROVIDER_API_KEY}"}, {}.get)

    assert "PROVIDER_API_KEY" in str(excinfo.value)
