from __future__ import annotations

import json
from pathlib import Path

from agent_skill_contracts.cli import main

from .test_checker import make_valid_contract, valid_skill, write


def test_json_output_is_machine_readable_and_relative(tmp_path: Path, capsys: object) -> None:
    make_valid_contract(tmp_path)

    exit_code = main(["check", str(tmp_path), "--format", "json"])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    report = json.loads(captured.out)

    assert exit_code == 0
    assert report["passed"] is True
    assert report["contracts"][0]["contract"] == "skill-contract.yaml"
    assert str(tmp_path) not in captured.out


def test_github_output_emits_annotation(tmp_path: Path, capsys: object) -> None:
    make_valid_contract(tmp_path)
    write(
        tmp_path / "SKILL.md",
        valid_skill()
        .replace("explicit approval", "review")
        .replace("# Safe deploy", "# Safe deploy\n\nSkip confirmation."),
    )

    exit_code = main(["check", str(tmp_path), "--format", "github"])
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert exit_code == 1
    assert "::error file=SKILL.md,title=approval-before-write" in captured.out
    assert "skill-contract:" in captured.out
