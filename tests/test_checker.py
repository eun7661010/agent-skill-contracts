from __future__ import annotations

from pathlib import Path

import pytest

from agent_skill_contracts.checker import check_path


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def valid_skill() -> str:
    return """---
name: safe-deploy
description: Deploy a synthetic service after approval.
allowed-tools: Read Bash
---

# Safe deploy

Ask for explicit approval before changing remote state.
Read references/safety.md before running deployment commands.
"""


def valid_contract() -> str:
    return """version: 1
skill: .
rules:
  - id: approval-before-write
    target: SKILL.md
    require:
      any:
        - text: explicit approval
        - regex: ask\\s+for\\s+approval
    forbid:
      - text: skip confirmation
files:
  required:
    - references/safety.md
references:
  required:
    - references/safety.md
frontmatter:
  required_fields: [name, description]
  required_tools: [Read, Bash]
portability:
  forbid_personal_paths: true
"""


def make_valid_contract(root: Path) -> None:
    write(root / "SKILL.md", valid_skill())
    write(root / "references" / "safety.md", "# Safety\n\nUse a dry run first.\n")
    write(root / "skill-contract.yaml", valid_contract())


def test_complete_contract_passes(tmp_path: Path) -> None:
    make_valid_contract(tmp_path)

    result = check_path(tmp_path)

    assert result.exit_code == 0
    assert result.passed
    assert result.to_dict()["summary"] == {
        "contracts": 1,
        "passed": 1,
        "failed": 0,
        "findings": 0,
        "config_issues": 0,
    }


def test_required_and_forbidden_patterns_report_findings(tmp_path: Path) -> None:
    make_valid_contract(tmp_path)
    write(
        tmp_path / "SKILL.md",
        valid_skill()
        .replace("explicit approval", "a review")
        .replace("# Safe deploy", "# Safe deploy\n\nSkip confirmation when rushed."),
    )

    result = check_path(tmp_path)

    assert result.exit_code == 1
    findings = result.results[0].findings
    assert {finding.kind for finding in findings} == {
        "forbidden_pattern_found",
        "required_alternative_missing",
    }
    forbidden = next(finding for finding in findings if finding.kind == "forbidden_pattern_found")
    assert forbidden.line == 9


def test_missing_file_reference_and_tool_are_reported(tmp_path: Path) -> None:
    make_valid_contract(tmp_path)
    (tmp_path / "references" / "safety.md").unlink()
    write(tmp_path / "SKILL.md", valid_skill().replace("Read Bash", "Read"))

    result = check_path(tmp_path)

    kinds = {finding.kind for finding in result.results[0].findings}
    assert kinds == {
        "required_file_missing",
        "required_reference_missing",
        "required_tool_missing",
    }


@pytest.mark.parametrize(
    "synthetic_path",
    [
        "C:\\Users\\sample-user\\private\\notes.txt",
        "/Users/sample-user/private/notes.txt",
        "/home/sample-user/private/notes.txt",
    ],
)
def test_personal_absolute_paths_are_detected(tmp_path: Path, synthetic_path: str) -> None:
    make_valid_contract(tmp_path)
    write(tmp_path / "references" / "safety.md", f"Do not embed {synthetic_path}\n")

    result = check_path(tmp_path)

    finding = next(
        finding
        for finding in result.results[0].findings
        if finding.kind == "personal_absolute_path"
    )
    assert finding.file == "references/safety.md"
    assert synthetic_path not in finding.message


def test_allowed_synthetic_path_can_be_used_as_a_negative_fixture(tmp_path: Path) -> None:
    make_valid_contract(tmp_path)
    write(tmp_path / "references" / "safety.md", "Reject /home/example-user/private.txt\n")
    write(
        tmp_path / "skill-contract.yaml",
        valid_contract() + "  allow:\n" + "    - regex: /home/example-user/\\S+\n",
    )

    result = check_path(tmp_path)

    assert result.exit_code == 0


def test_json_contract_and_recursive_discovery(tmp_path: Path) -> None:
    first = tmp_path / "skills" / "first"
    second = tmp_path / "skills" / "second"
    make_valid_contract(first)
    make_valid_contract(second)
    (second / "skill-contract.yaml").unlink()
    write(
        second / "skill-contract.json",
        """{
  "version": 1,
  "skill": ".",
  "rules": [{"id": "has-title", "require": {"all": ["# Safe deploy"]}}]
}
""",
    )

    result = check_path(tmp_path)

    assert result.exit_code == 0
    assert len(result.results) == 2
    assert all(not Path(item.contract).is_absolute() for item in result.results)


def test_path_escape_is_a_config_error(tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    write(skill / "SKILL.md", valid_skill())
    write(
        skill / "skill-contract.yaml",
        """version: 1
rules:
  - id: escape
    target: ../outside.md
    require:
      all: [unsafe]
""",
    )

    result = check_path(skill)

    assert result.exit_code == 2
    assert "escapes its allowed directory" in result.config_issues[0].message


def test_duplicate_rule_id_is_a_config_error(tmp_path: Path) -> None:
    write(tmp_path / "SKILL.md", valid_skill())
    write(
        tmp_path / "skill-contract.yaml",
        """version: 1
rules:
  - id: duplicate
    require: {all: [Safe]}
  - id: duplicate
    forbid: [unsafe]
""",
    )

    result = check_path(tmp_path)

    assert result.exit_code == 2
    assert "Duplicate rule id" in result.config_issues[0].message


def test_missing_contract_is_a_config_error(tmp_path: Path) -> None:
    result = check_path(tmp_path)

    assert result.exit_code == 2
    assert "No contract found" in result.config_issues[0].message
