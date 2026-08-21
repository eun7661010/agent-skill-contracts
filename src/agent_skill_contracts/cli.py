from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_skill_contracts import __version__
from agent_skill_contracts.checker import check_path
from agent_skill_contracts.models import RunResult


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill-contract",
        description="Check deterministic behavioral contracts for SKILL.md files.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser(
        "check", help="Check one contract or discover contracts below a path."
    )
    check.add_argument("path", nargs="?", default=".", help="Contract file or directory to scan.")
    check.add_argument(
        "--format",
        choices=("text", "json", "github"),
        default="text",
        help="Output format. 'github' emits workflow annotations.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run = check_path(Path(args.path))
    if args.format == "json":
        print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    elif args.format == "github":
        _print_github(run)
    else:
        _print_text(run)
    return run.exit_code


def _print_text(run: RunResult) -> None:
    for issue in run.config_issues:
        print(f"CONFIG ERROR {issue.contract}: {issue.message}")
    for result in run.results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} {result.contract} (skill: {result.skill})")
        for finding in result.findings:
            location = finding.file
            if finding.line is not None:
                location += f":{finding.line}"
            print(
                f"  [{finding.severity.upper()}] {finding.rule_id} "
                f"({finding.kind}) {location}: {finding.message}"
            )
    summary = run.to_dict()["summary"]
    print(
        "Summary: "
        f"{summary['contracts']} contract(s), {summary['passed']} passed, "
        f"{summary['failed']} failed, {summary['findings']} finding(s), "
        f"{summary['config_issues']} config issue(s)"
    )


def _print_github(run: RunResult) -> None:
    for issue in run.config_issues:
        print(
            f"::error file={_escape_property(issue.contract)},title=Invalid skill contract::"
            f"{_escape_message(issue.message)}"
        )
    for result in run.results:
        for finding in result.findings:
            file_path = _join_display(result.skill, finding.file)
            properties = [
                f"file={_escape_property(file_path)}",
                f"title={_escape_property(finding.rule_id)}",
            ]
            if finding.line is not None:
                properties.append(f"line={finding.line}")
            print(f"::error {','.join(properties)}::{_escape_message(finding.message)}")
    summary = run.to_dict()["summary"]
    print(
        "skill-contract: "
        f"{summary['passed']}/{summary['contracts']} passed; "
        f"{summary['findings']} finding(s); {summary['config_issues']} config issue(s)"
    )


def _join_display(skill: str, file: str) -> str:
    if skill in ("", "."):
        return file
    return f"{skill.rstrip('/')}/{file.lstrip('/')}"


def _escape_property(value: str) -> str:
    return _escape_message(value).replace(":", "%3A").replace(",", "%2C")


def _escape_message(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
