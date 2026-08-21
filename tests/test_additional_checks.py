from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from agent_skill_contracts.checker import check_path
from agent_skill_contracts.cli import main

from .test_checker import make_valid_contract, valid_contract, valid_skill, write


def test_reference_must_be_mentioned(tmp_path: Path) -> None:
    make_valid_contract(tmp_path)
    write(
        tmp_path / "SKILL.md",
        valid_skill().replace(
            "Read references/safety.md before running deployment commands.\n", ""
        ),
    )

    result = check_path(tmp_path)

    assert result.exit_code == 1
    assert any(finding.kind == "reference_not_mentioned" for finding in result.results[0].findings)


def test_reference_can_select_another_source(tmp_path: Path) -> None:
    write(tmp_path / "SKILL.md", valid_skill())
    write(tmp_path / "references" / "safety.md", "See scripts/check.py.\n")
    write(tmp_path / "scripts" / "check.py", "print('synthetic')\n")
    write(
        tmp_path / "skill-contract.yaml",
        """version: 1
references:
  required:
    - path: scripts/check.py
      mentioned_in: references/safety.md
""",
    )

    result = check_path(tmp_path)

    assert result.exit_code == 0


def test_missing_reference_source_is_reported(tmp_path: Path) -> None:
    write(tmp_path / "SKILL.md", valid_skill())
    write(tmp_path / "references" / "safety.md", "Synthetic reference.\n")
    write(
        tmp_path / "skill-contract.yaml",
        """version: 1
references:
  required:
    - path: references/safety.md
      mentioned_in: references/missing-index.md
""",
    )

    result = check_path(tmp_path)

    assert result.exit_code == 1
    assert result.results[0].findings[0].kind == "reference_source_missing"


def test_frontmatter_findings_without_metadata(tmp_path: Path) -> None:
    write(tmp_path / "SKILL.md", "# No metadata\n")
    write(
        tmp_path / "skill-contract.yaml",
        """version: 1
frontmatter:
  required_fields: [name, description]
  required_tools: [Read]
""",
    )

    result = check_path(tmp_path)

    assert result.exit_code == 1
    kinds = [finding.kind for finding in result.results[0].findings]
    assert kinds.count("required_frontmatter_missing") == 2
    assert "required_tool_missing" in kinds


def test_frontmatter_only_contract_reports_missing_skill(tmp_path: Path) -> None:
    write(tmp_path / "placeholder.txt", "keep directory present\n")
    write(
        tmp_path / "skill-contract.yaml",
        "version: 1\nfrontmatter:\n  required_fields: [name]\n",
    )

    result = check_path(tmp_path)

    assert result.exit_code == 1
    assert result.results[0].findings[0].kind == "skill_file_missing"


@pytest.mark.parametrize(
    ("skill_text", "message"),
    [
        ("---\nname: open\n# missing close\n", "frontmatter is not closed"),
        ("---\nname: [\n---\n# invalid\n", "Invalid SKILL.md frontmatter"),
        ("---\n- name\n- value\n---\n# list\n", "frontmatter must be an object"),
        ("---\nname: x\nallowed-tools: {Read: true}\n---\n# invalid tools\n", "allowed-tools"),
    ],
)
def test_invalid_frontmatter_is_a_config_error(
    tmp_path: Path, skill_text: str, message: str
) -> None:
    write(tmp_path / "SKILL.md", skill_text)
    write(
        tmp_path / "skill-contract.yaml",
        "version: 1\nfrontmatter:\n  required_tools: [Read]\n",
    )

    result = check_path(tmp_path)

    assert result.exit_code == 2
    assert message in result.config_issues[0].message


def test_tool_lists_and_scoped_tool_names_are_supported(tmp_path: Path) -> None:
    write(
        tmp_path / "SKILL.md",
        """---
name: tools
description: Synthetic tools.
allowed-tools:
  - Read
  - Bash(git:*)
---
# Tools
""",
    )
    write(
        tmp_path / "skill-contract.yaml",
        "version: 1\nfrontmatter:\n  required_tools: [Read, Bash]\n",
    )

    result = check_path(tmp_path)

    assert result.exit_code == 0


def test_portability_scan_and_exclude_are_respected(tmp_path: Path) -> None:
    write(tmp_path / "SKILL.md", valid_skill())
    write(tmp_path / "references" / "scan.md", "Synthetic /home/sample-user/a.txt\n")
    write(tmp_path / "references" / "excluded.md", "Synthetic /home/sample-user/b.txt\n")
    write(
        tmp_path / "skill-contract.yaml",
        """version: 1
rules:
  - id: base
    require: {all: [Safe deploy]}
portability:
  scan: [references/*.md]
  exclude: [references/excluded.md]
  allow:
    - regex: /home/sample-user/a\\.txt
""",
    )

    result = check_path(tmp_path)

    assert result.exit_code == 0


def test_portability_can_be_disabled(tmp_path: Path) -> None:
    write(tmp_path / "SKILL.md", valid_skill() + "\nSynthetic /home/sample-user/private.txt\n")
    write(
        tmp_path / "skill-contract.yaml",
        "version: 1\nrules:\n  - id: base\n    require: {all: [Safe deploy]}\nportability: false\n",
    )

    result = check_path(tmp_path)

    assert result.exit_code == 0


def test_external_symlink_is_rejected_or_platform_skips(tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    external = tmp_path / "outside.txt"
    write(skill / "SKILL.md", valid_skill())
    write(external, "Synthetic outside file.\n")
    link = skill / "references" / "outside.txt"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(external)
    except OSError as exc:
        pytest.skip(f"Symlink creation is unavailable: {exc}")
    write(
        skill / "skill-contract.yaml",
        "version: 1\nrules:\n  - id: base\n    require: {all: [Safe deploy]}\n",
    )

    result = check_path(skill)

    assert result.exit_code == 1
    assert any(finding.kind == "external_symlink" for finding in result.results[0].findings)


def test_text_output_and_invalid_path_output(tmp_path: Path, capsys: object) -> None:
    make_valid_contract(tmp_path)

    passed = main(["check", str(tmp_path)])
    first = capsys.readouterr()  # type: ignore[attr-defined]
    failed = main(["check", str(tmp_path / "missing"), "--format", "github"])
    second = capsys.readouterr()  # type: ignore[attr-defined]

    assert passed == 0
    assert "PASS skill-contract.yaml" in first.out
    assert failed == 2
    assert "::error file=" in second.out
    assert "Invalid skill contract" in second.out


def test_schema_accepts_bundled_examples() -> None:
    root = Path(__file__).parents[1]
    schema = json.loads((root / "schema" / "skill-contract.schema.json").read_text("utf-8"))
    validator = Draft202012Validator(schema)

    for contract_path in (root / "examples").glob("*/skill-contract.yaml"):
        contract = yaml.safe_load(contract_path.read_text("utf-8"))
        errors = list(validator.iter_errors(contract))
        assert not errors, f"{contract_path}: {errors}"


def test_direct_contract_file_and_extension_fields(tmp_path: Path) -> None:
    write(tmp_path / "SKILL.md", valid_skill())
    write(
        tmp_path / "skill-contract.json",
        json.dumps(
            {
                "version": 1,
                "x-owner": "synthetic-team",
                "rules": [
                    {
                        "id": "case-sensitive",
                        "x-note": "synthetic",
                        "require": {"all": [{"text": "Safe deploy", "case_sensitive": True}]},
                    }
                ],
            }
        ),
    )

    result = check_path(tmp_path / "skill-contract.json")

    assert result.exit_code == 0
    assert result.results[0].contract == "skill-contract.json"


def test_default_contract_fixture_is_still_valid() -> None:
    assert "portability:" in valid_contract()
