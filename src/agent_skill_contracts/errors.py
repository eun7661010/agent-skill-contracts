from __future__ import annotations

from pathlib import Path


class ContractError(Exception):
    """Base exception for contract loading and validation errors."""


class ContractConfigError(ContractError):
    """Raised when a contract cannot be interpreted safely."""

    def __init__(self, message: str, *, path: Path | None = None) -> None:
        super().__init__(message)
        self.path = path
