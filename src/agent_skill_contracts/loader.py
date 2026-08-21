from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from agent_skill_contracts.errors import ContractConfigError


def load_contract(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ContractConfigError(f"Cannot read contract: {exc}", path=path) from exc

    try:
        data = json.loads(text) if path.suffix.casefold() == ".json" else yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ContractConfigError(f"Invalid contract syntax: {exc}", path=path) from exc

    if not isinstance(data, dict):
        raise ContractConfigError("Contract root must be an object.", path=path)
    return data
