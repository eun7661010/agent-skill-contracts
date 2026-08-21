from __future__ import annotations

from pathlib import Path

import pytest

from agent_skill_contracts.checker import check_path

from .test_checker import valid_skill, write


def run_contract(tmp_path: Path, contract: str, *, skill_text: str | None = None):
    if skill_text is not None:
        write(tmp_path / "SKILL.md", skill_text)
    write(tmp_path / "skill-contract.yaml", contract)
    return check_path(tmp_path)


@pytest.mark.parametrize(
    ("contract", "message"),
    [
        ("- version\n- 1\n", "Contract root must be an object"),
        ("version: 2\nrules: []\n", "'version' must be 1"),
        ("version: 1\nunknown: true\n", "Unknown top-level field"),
        ("version: 1\nportability: false\n", "at least one assertion"),
        ("version: 1\nskill: ''\nrules: []\n", "'skill' must be a non-empty"),
        ("version: 1\nskill: missing\nrules: []\n", "Skill directory does not exist"),
        ("version: 1\nskill: ../outside\nrules: []\n", "escapes its allowed directory"),
        ("version: 1\nrules: invalid\n", "'rules' must be a list"),
        ("version: 1\nrules: [invalid]\n", "rules[0] must be an object"),
        (
            "version: 1\nrules:\n  - id: Bad ID\n    require: {all: [x]}\n",
            "must match",
        ),
        (
            "version: 1\nrules:\n  - id: one\n    unexpected: true\n    require: {all: [x]}\n",
            "unknown field",
        ),
        ("version: 1\nrules:\n  - id: empty\n", "must declare 'require' or 'forbid'"),
        (
            "version: 1\nrules:\n  - id: description\n"
            "    description: 3\n    require: {all: [x]}\n",
            "description must be a string",
        ),
        (
            "version: 1\nrules:\n  - id: target\n    target: ''\n    require: {all: [x]}\n",
            "target must be a path",
        ),
        (
            "version: 1\nrules:\n  - id: require\n    require: invalid\n",
            "require must be an object",
        ),
        (
            "version: 1\nrules:\n  - id: require\n    require: {other: [x]}\n",
            "require has unknown field",
        ),
        (
            "version: 1\nrules:\n  - id: require\n    require: {}\n",
            "require cannot be empty",
        ),
        (
            "version: 1\nrules:\n  - id: patterns\n    require: {all: []}\n",
            "must be a non-empty list",
        ),
        (
            "version: 1\nrules:\n  - id: patterns\n    require: {all: [3]}\n",
            "must be a string or object",
        ),
        (
            "version: 1\nrules:\n  - id: patterns\n    require: {all: [{text: x, extra: y}]}\n",
            "unknown field",
        ),
        (
            "version: 1\nrules:\n  - id: patterns\n    require: {all: [{text: x, regex: y}]}\n",
            "exactly one",
        ),
        (
            "version: 1\nrules:\n  - id: patterns\n    require: {all: [{text: ''}]}\n",
            "must be a non-empty string",
        ),
        (
            "version: 1\nrules:\n  - id: patterns\n"
            "    require: {all: [{text: x, case_sensitive: 'yes'}]}\n",
            "case_sensitive must be a boolean",
        ),
        (
            "version: 1\nrules:\n  - id: patterns\n    require: {all: [{regex: '['}]}\n",
            "regex is invalid",
        ),
    ],
)
def test_invalid_contracts_fail_closed(tmp_path: Path, contract: str, message: str) -> None:
    result = run_contract(tmp_path, contract, skill_text=valid_skill())

    assert result.exit_code == 2
    assert message in result.config_issues[0].message


def test_invalid_yaml_and_missing_path_are_config_errors(tmp_path: Path) -> None:
    invalid = run_contract(tmp_path, "version: [\n", skill_text=valid_skill())
    missing = check_path(tmp_path / "does-not-exist")

    assert invalid.exit_code == 2
    assert "Invalid contract syntax" in invalid.config_issues[0].message
    assert missing.exit_code == 2
    assert "does not exist" in missing.config_issues[0].message


@pytest.mark.parametrize("suffix", ["yaml", "json"])
def test_duplicate_mapping_keys_are_rejected(tmp_path: Path, suffix: str) -> None:
    write(tmp_path / "SKILL.md", valid_skill())
    if suffix == "yaml":
        contract = """version: 1
rules:
  - id: approval
    require:
      all: [MUST-PRESERVE]
    require:
      all: [Safe deploy]
portability: false
"""
    else:
        contract = """{
  "version": 1,
  "rules": [{
    "id": "approval",
    "require": {"all": ["MUST-PRESERVE"]},
    "require": {"all": ["Safe deploy"]}
  }],
  "portability": false
}
"""
    write(tmp_path / f"skill-contract.{suffix}", contract)

    result = check_path(tmp_path)

    assert result.exit_code == 2
    assert "Duplicate" in result.config_issues[0].message


def test_missing_target_is_a_behavioral_finding(tmp_path: Path) -> None:
    result = run_contract(
        tmp_path,
        """version: 1
rules:
  - id: missing-target
    target: references/missing.md
    require: {all: [required]}
""",
        skill_text=valid_skill(),
    )

    assert result.exit_code == 1
    assert result.results[0].findings[0].kind == "target_missing"


@pytest.mark.parametrize(
    ("section", "message"),
    [
        ("files: []", "'files' must contain only"),
        ("files: {required: []}", "files.required must be a non-empty"),
        ("references: []", "'references' must contain only"),
        ("references: {required: []}", "references.required must be a non-empty"),
        ("references: {required: [3]}", "must be a path or object"),
        (
            "references: {required: [{path: references/a.md, mentioned_in: 3}]}",
            "paths must be strings",
        ),
        ("frontmatter: []", "'frontmatter' must be an object"),
        ("frontmatter: {unexpected: true}", "frontmatter has unknown field"),
        ("portability: invalid", "'portability' must be an object"),
        ("portability: {unexpected: true}", "portability has unknown field"),
        (
            "portability: {forbid_personal_paths: invalid}",
            "portability boolean fields",
        ),
        ("portability: {scan: invalid}", "portability.scan must be a non-empty"),
        ("portability: {exclude: invalid}", "portability.exclude must be a non-empty"),
    ],
)
def test_invalid_sections_are_rejected(tmp_path: Path, section: str, message: str) -> None:
    result = run_contract(
        tmp_path,
        f"version: 1\nrules:\n  - id: base\n    require: {{all: [Safe]}}\n{section}\n",
        skill_text=valid_skill(),
    )

    assert result.exit_code == 2
    assert message in result.config_issues[0].message
