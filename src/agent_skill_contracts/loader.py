from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

from agent_skill_contracts.errors import ContractConfigError


class UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate keys at every mapping depth."""

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Any, Any]:
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "Mapping keys must be hashable.",
                    key_node.start_mark,
                ) from exc
            if duplicate:
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"Duplicate mapping key: {key!r}.",
                    key_node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def load_yaml(text: str) -> Any:
    return yaml.load(text, Loader=UniqueKeySafeLoader)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate object key: {key!r}.")
        value[key] = item
    return value


def load_contract(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ContractConfigError(f"Cannot read contract: {exc}", path=path) from exc

    try:
        data = (
            json.loads(text, object_pairs_hook=_unique_json_object)
            if path.suffix.casefold() == ".json"
            else load_yaml(text)
        )
    except (json.JSONDecodeError, ValueError, yaml.YAMLError) as exc:
        raise ContractConfigError(f"Invalid contract syntax: {exc}", path=path) from exc

    if not isinstance(data, dict):
        raise ContractConfigError("Contract root must be an object.", path=path)
    return data
