from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    kind: str
    message: str
    file: str
    line: int | None = None
    severity: str = "error"

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "rule_id": self.rule_id,
            "kind": self.kind,
            "severity": self.severity,
            "message": self.message,
            "file": self.file,
        }
        if self.line is not None:
            data["line"] = self.line
        return data


@dataclass(slots=True)
class ContractResult:
    contract: str
    skill: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.findings

    def to_dict(self) -> dict[str, object]:
        return {
            "contract": self.contract,
            "skill": self.skill,
            "passed": self.passed,
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True, slots=True)
class ConfigIssue:
    contract: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"contract": self.contract, "message": self.message}


@dataclass(slots=True)
class RunResult:
    results: list[ContractResult] = field(default_factory=list)
    config_issues: list[ConfigIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.config_issues and all(result.passed for result in self.results)

    @property
    def exit_code(self) -> int:
        if self.config_issues:
            return 2
        if not self.passed:
            return 1
        return 0

    def to_dict(self) -> dict[str, object]:
        passed = sum(result.passed for result in self.results)
        findings = sum(len(result.findings) for result in self.results)
        return {
            "schema_version": 1,
            "passed": self.passed,
            "contracts": [result.to_dict() for result in self.results],
            "config_issues": [issue.to_dict() for issue in self.config_issues],
            "summary": {
                "contracts": len(self.results),
                "passed": passed,
                "failed": len(self.results) - passed,
                "findings": findings,
                "config_issues": len(self.config_issues),
            },
        }
