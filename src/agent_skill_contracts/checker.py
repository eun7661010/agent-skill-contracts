from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import yaml

from agent_skill_contracts.errors import ContractConfigError
from agent_skill_contracts.loader import load_contract, load_yaml
from agent_skill_contracts.models import ConfigIssue, ContractResult, Finding, RunResult

CONTRACT_NAMES = ("skill-contract.yaml", "skill-contract.yml", "skill-contract.json")
IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}
TEXT_SUFFIXES = {
    "",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
RULE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
PERSONAL_PATH_PATTERNS = (
    re.compile(
        r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]+)Users[\\/]+"
        r"[^\\/\s\"'<>`]+(?:[\\/]+[^\\/\s\"'<>`]*)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![A-Za-z0-9])/(?:Users|home)/[^/\s\"'<>`]+"
        r"(?:/[^/\s\"'<>`]*)?",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True, slots=True)
class TextPattern:
    kind: str
    value: str
    case_sensitive: bool = False


def discover_contracts(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise ContractConfigError("Check path does not exist or is not a directory.", path=path)

    contracts: list[Path] = []
    for candidate in path.rglob("*"):
        if not candidate.is_file() or candidate.name not in CONTRACT_NAMES:
            continue
        try:
            relative_parts = candidate.relative_to(path).parts
        except ValueError:
            continue
        if any(part in IGNORED_DIRECTORIES for part in relative_parts):
            continue
        contracts.append(candidate)
    return sorted(contracts, key=lambda item: item.as_posix().casefold())


def check_path(path: Path) -> RunResult:
    requested = path.resolve()
    base = requested if requested.is_dir() else requested.parent
    run = RunResult()
    try:
        contracts = discover_contracts(requested)
    except ContractConfigError as exc:
        run.config_issues.append(ConfigIssue(_display_path(exc.path or requested, base), str(exc)))
        return run

    if not contracts:
        names = ", ".join(CONTRACT_NAMES)
        run.config_issues.append(
            ConfigIssue(_display_path(requested, base), f"No contract found. Expected: {names}.")
        )
        return run

    for contract in contracts:
        try:
            run.results.append(check_contract(contract, display_base=base))
        except ContractConfigError as exc:
            issue_path = exc.path or contract
            run.config_issues.append(ConfigIssue(_display_path(issue_path, base), str(exc)))
    return run


def check_contract(contract_path: Path, *, display_base: Path | None = None) -> ContractResult:
    contract_path = contract_path.resolve()
    base = (display_base or contract_path.parent).resolve()
    data = load_contract(contract_path)
    _validate_top_level(data, contract_path)

    contract_root = contract_path.parent.resolve()
    skill_value = data.get("skill", ".")
    if not isinstance(skill_value, str) or not skill_value.strip():
        raise ContractConfigError("'skill' must be a non-empty relative path.", path=contract_path)
    skill_dir = _safe_join(contract_root, skill_value, "skill", contract_path)
    if not skill_dir.is_dir():
        raise ContractConfigError(
            f"Skill directory does not exist: {skill_value}", path=contract_path
        )

    contract_display = _display_path(contract_path, base)
    skill_display = _display_path(skill_dir, base)
    findings: list[Finding] = []
    assertion_count = 0

    rules = data.get("rules", [])
    if not isinstance(rules, list):
        raise ContractConfigError("'rules' must be a list.", path=contract_path)
    seen_rule_ids: set[str] = set()
    for index, raw_rule in enumerate(rules):
        rule_id = _validate_rule(raw_rule, index, seen_rule_ids, contract_path)
        seen_rule_ids.add(rule_id)
        findings.extend(_check_rule(raw_rule, rule_id, skill_dir, contract_path))
        assertion_count += 1

    files = data.get("files")
    if files is not None:
        findings.extend(_check_required_files(files, skill_dir, contract_path))
        assertion_count += 1

    references = data.get("references")
    if references is not None:
        findings.extend(_check_references(references, skill_dir, contract_path))
        assertion_count += 1

    frontmatter = data.get("frontmatter")
    if frontmatter is not None:
        findings.extend(_check_frontmatter(frontmatter, skill_dir, contract_path))
        assertion_count += 1

    portability = data.get("portability", {"forbid_personal_paths": True})
    if portability is not False:
        findings.extend(_check_portability(portability, skill_dir, contract_path))
        assertion_count += 1

    if assertion_count == 0:
        raise ContractConfigError(
            "Contract must declare at least one assertion.", path=contract_path
        )

    findings.sort(key=lambda finding: (finding.file.casefold(), finding.line or 0, finding.rule_id))
    return ContractResult(contract=contract_display, skill=skill_display, findings=findings)


def _validate_top_level(data: dict[str, Any], path: Path) -> None:
    version = data.get("version")
    if version != 1:
        raise ContractConfigError("'version' must be 1.", path=path)
    allowed = {
        "version",
        "skill",
        "rules",
        "files",
        "references",
        "frontmatter",
        "portability",
    }
    unknown = sorted(key for key in data if key not in allowed and not key.startswith("x-"))
    if unknown:
        raise ContractConfigError(f"Unknown top-level field(s): {', '.join(unknown)}.", path=path)


def _validate_rule(
    rule: Any,
    index: int,
    seen_rule_ids: set[str],
    path: Path,
) -> str:
    if not isinstance(rule, dict):
        raise ContractConfigError(f"rules[{index}] must be an object.", path=path)
    allowed = {"id", "description", "target", "require", "forbid"}
    unknown = sorted(key for key in rule if key not in allowed and not key.startswith("x-"))
    if unknown:
        raise ContractConfigError(
            f"rules[{index}] has unknown field(s): {', '.join(unknown)}.", path=path
        )
    rule_id = rule.get("id")
    if not isinstance(rule_id, str) or not RULE_ID.fullmatch(rule_id):
        raise ContractConfigError(f"rules[{index}].id must match {RULE_ID.pattern!r}.", path=path)
    if rule_id in seen_rule_ids:
        raise ContractConfigError(f"Duplicate rule id: {rule_id}.", path=path)
    if "require" not in rule and "forbid" not in rule:
        raise ContractConfigError(
            f"Rule '{rule_id}' must declare 'require' or 'forbid'.", path=path
        )
    description = rule.get("description")
    if description is not None and not isinstance(description, str):
        raise ContractConfigError(f"Rule '{rule_id}'.description must be a string.", path=path)
    return rule_id


def _check_rule(
    rule: dict[str, Any],
    rule_id: str,
    skill_dir: Path,
    contract_path: Path,
) -> list[Finding]:
    target_value = rule.get("target", "SKILL.md")
    if not isinstance(target_value, str) or not target_value.strip():
        raise ContractConfigError(f"Rule '{rule_id}'.target must be a path.", path=contract_path)
    target = _safe_join(skill_dir, target_value, f"rule '{rule_id}' target", contract_path)
    target_display = _relative_display(target, skill_dir)
    if not target.is_file():
        return [
            Finding(
                rule_id=rule_id,
                kind="target_missing",
                message="The rule target file does not exist.",
                file=target_display,
            )
        ]
    try:
        text = target.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ContractConfigError(
            f"Cannot read target for rule '{rule_id}': {exc}", path=target
        ) from exc

    findings: list[Finding] = []
    if "require" in rule:
        requirement = rule["require"]
        if not isinstance(requirement, dict):
            raise ContractConfigError(
                f"Rule '{rule_id}'.require must be an object.", path=contract_path
            )
        unknown = set(requirement) - {"all", "any"}
        if unknown:
            raise ContractConfigError(
                f"Rule '{rule_id}'.require has unknown field(s): {', '.join(sorted(unknown))}.",
                path=contract_path,
            )
        if not requirement:
            raise ContractConfigError(
                f"Rule '{rule_id}'.require cannot be empty.", path=contract_path
            )
        if "all" in requirement:
            patterns = _parse_pattern_list(
                requirement["all"], f"Rule '{rule_id}'.require.all", contract_path
            )
            for pattern in patterns:
                if _search_pattern(text, pattern) is None:
                    findings.append(
                        Finding(
                            rule_id=rule_id,
                            kind="required_pattern_missing",
                            message=f"Required {_pattern_label(pattern)} was not found.",
                            file=target_display,
                        )
                    )
        if "any" in requirement:
            patterns = _parse_pattern_list(
                requirement["any"], f"Rule '{rule_id}'.require.any", contract_path
            )
            if all(_search_pattern(text, pattern) is None for pattern in patterns):
                labels = ", ".join(_pattern_label(pattern) for pattern in patterns)
                findings.append(
                    Finding(
                        rule_id=rule_id,
                        kind="required_alternative_missing",
                        message=f"None of the required alternatives was found: {labels}.",
                        file=target_display,
                    )
                )

    if "forbid" in rule:
        patterns = _parse_pattern_list(rule["forbid"], f"Rule '{rule_id}'.forbid", contract_path)
        for pattern in patterns:
            match = _search_pattern(text, pattern)
            if match is not None:
                findings.append(
                    Finding(
                        rule_id=rule_id,
                        kind="forbidden_pattern_found",
                        message=f"Forbidden {_pattern_label(pattern)} matched.",
                        file=target_display,
                        line=_line_number(text, match[0]),
                    )
                )
    return findings


def _parse_pattern_list(value: Any, label: str, path: Path) -> list[TextPattern]:
    if not isinstance(value, list) or not value:
        raise ContractConfigError(f"{label} must be a non-empty list.", path=path)
    return [_parse_pattern(item, f"{label}[{index}]", path) for index, item in enumerate(value)]


def _parse_pattern(value: Any, label: str, path: Path) -> TextPattern:
    if isinstance(value, str) and value:
        return TextPattern(kind="text", value=value)
    if not isinstance(value, dict):
        raise ContractConfigError(f"{label} must be a string or object.", path=path)
    allowed = {"text", "regex", "case_sensitive"}
    unknown = set(value) - allowed
    if unknown:
        raise ContractConfigError(
            f"{label} has unknown field(s): {', '.join(sorted(unknown))}.", path=path
        )
    kinds = [kind for kind in ("text", "regex") if kind in value]
    if len(kinds) != 1:
        raise ContractConfigError(
            f"{label} must contain exactly one of 'text' or 'regex'.", path=path
        )
    kind = kinds[0]
    pattern_value = value[kind]
    if not isinstance(pattern_value, str) or not pattern_value:
        raise ContractConfigError(f"{label}.{kind} must be a non-empty string.", path=path)
    case_sensitive = value.get("case_sensitive", False)
    if not isinstance(case_sensitive, bool):
        raise ContractConfigError(f"{label}.case_sensitive must be a boolean.", path=path)
    if kind == "regex":
        try:
            re.compile(pattern_value)
        except re.error as exc:
            raise ContractConfigError(f"{label}.regex is invalid: {exc}", path=path) from exc
    return TextPattern(kind=kind, value=pattern_value, case_sensitive=case_sensitive)


def _search_pattern(text: str, pattern: TextPattern) -> tuple[int, int] | None:
    if pattern.kind == "text":
        haystack = text if pattern.case_sensitive else text.casefold()
        needle = pattern.value if pattern.case_sensitive else pattern.value.casefold()
        index = haystack.find(needle)
        return None if index < 0 else (index, index + len(pattern.value))
    flags = 0 if pattern.case_sensitive else re.IGNORECASE
    match = re.search(pattern.value, text, flags)
    return None if match is None else match.span()


def _pattern_label(pattern: TextPattern) -> str:
    return f"{pattern.kind} pattern {pattern.value!r}"


def _check_required_files(value: Any, skill_dir: Path, path: Path) -> list[Finding]:
    if not isinstance(value, dict) or set(value) != {"required"}:
        raise ContractConfigError("'files' must contain only a 'required' list.", path=path)
    required = _string_list(value["required"], "files.required", path)
    findings: list[Finding] = []
    for relative in required:
        target = _safe_join(skill_dir, relative, "required file", path)
        if not target.is_file():
            findings.append(
                Finding(
                    rule_id="files.required",
                    kind="required_file_missing",
                    message="A required file does not exist.",
                    file=_relative_display(target, skill_dir),
                )
            )
    return findings


def _check_references(value: Any, skill_dir: Path, path: Path) -> list[Finding]:
    if not isinstance(value, dict) or set(value) != {"required"}:
        raise ContractConfigError("'references' must contain only a 'required' list.", path=path)
    raw_required = value["required"]
    if not isinstance(raw_required, list) or not raw_required:
        raise ContractConfigError("references.required must be a non-empty list.", path=path)
    findings: list[Finding] = []
    for index, item in enumerate(raw_required):
        if isinstance(item, str):
            reference_path = item
            mentioned_in = "SKILL.md"
        elif isinstance(item, dict) and set(item).issubset({"path", "mentioned_in"}):
            reference_path = item.get("path")
            mentioned_in = item.get("mentioned_in", "SKILL.md")
            if not isinstance(reference_path, str) or not isinstance(mentioned_in, str):
                raise ContractConfigError(
                    f"references.required[{index}] paths must be strings.", path=path
                )
        else:
            raise ContractConfigError(
                f"references.required[{index}] must be a path or object.", path=path
            )
        reference = _safe_join(skill_dir, reference_path, "required reference", path)
        mention_source = _safe_join(skill_dir, mentioned_in, "reference source", path)
        reference_display = _relative_display(reference, skill_dir)
        if not reference.is_file():
            findings.append(
                Finding(
                    rule_id="references.required",
                    kind="required_reference_missing",
                    message="A required reference file does not exist.",
                    file=reference_display,
                )
            )
            continue
        if not mention_source.is_file():
            findings.append(
                Finding(
                    rule_id="references.required",
                    kind="reference_source_missing",
                    message="The file that should mention the reference does not exist.",
                    file=_relative_display(mention_source, skill_dir),
                )
            )
            continue
        try:
            source_text = mention_source.read_text(encoding="utf-8-sig").replace("\\", "/")
        except (OSError, UnicodeError) as exc:
            raise ContractConfigError(
                f"Cannot read reference source: {exc}", path=mention_source
            ) from exc
        normalized_reference = Path(reference_path).as_posix()
        if normalized_reference not in source_text:
            findings.append(
                Finding(
                    rule_id="references.required",
                    kind="reference_not_mentioned",
                    message=(
                        "The required reference exists but is not mentioned by its source file."
                    ),
                    file=_relative_display(mention_source, skill_dir),
                )
            )
    return findings


def _check_frontmatter(value: Any, skill_dir: Path, path: Path) -> list[Finding]:
    if not isinstance(value, dict):
        raise ContractConfigError("'frontmatter' must be an object.", path=path)
    allowed = {"required_fields", "required_tools"}
    unknown = set(value) - allowed
    if unknown:
        raise ContractConfigError(
            f"frontmatter has unknown field(s): {', '.join(sorted(unknown))}.", path=path
        )
    skill_file = _safe_join(skill_dir, "SKILL.md", "frontmatter target", path)
    if not skill_file.is_file():
        return [
            Finding(
                rule_id="frontmatter",
                kind="skill_file_missing",
                message="SKILL.md does not exist.",
                file="SKILL.md",
            )
        ]
    try:
        text = skill_file.read_text(encoding="utf-8-sig")
        metadata = _parse_frontmatter(text, skill_file)
    except (OSError, UnicodeError) as exc:
        raise ContractConfigError(f"Cannot read SKILL.md: {exc}", path=skill_file) from exc

    findings: list[Finding] = []
    if "required_fields" in value:
        for field_name in _string_list(
            value["required_fields"], "frontmatter.required_fields", path
        ):
            if field_name not in metadata or metadata[field_name] in (None, "", []):
                findings.append(
                    Finding(
                        rule_id="frontmatter.required_fields",
                        kind="required_frontmatter_missing",
                        message=f"Required frontmatter field {field_name!r} is missing or empty.",
                        file="SKILL.md",
                    )
                )
    if "required_tools" in value:
        required_tools = _string_list(value["required_tools"], "frontmatter.required_tools", path)
        declared = metadata.get("allowed-tools", metadata.get("allowed_tools", []))
        declared_tools = _normalize_tools(declared, skill_file)
        for tool in required_tools:
            if tool.casefold() not in declared_tools:
                findings.append(
                    Finding(
                        rule_id="frontmatter.required_tools",
                        kind="required_tool_missing",
                        message=f"Required tool declaration {tool!r} is missing.",
                        file="SKILL.md",
                    )
                )
    return findings


def _parse_frontmatter(text: str, path: Path) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    closing = next(
        (index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"), None
    )
    if closing is None:
        raise ContractConfigError("SKILL.md frontmatter is not closed.", path=path)
    try:
        metadata = load_yaml("\n".join(lines[1:closing])) or {}
    except yaml.YAMLError as exc:
        raise ContractConfigError(f"Invalid SKILL.md frontmatter: {exc}", path=path) from exc
    if not isinstance(metadata, dict):
        raise ContractConfigError("SKILL.md frontmatter must be an object.", path=path)
    return metadata


def _normalize_tools(value: Any, path: Path) -> set[str]:
    if value in (None, ""):
        return set()
    if isinstance(value, str):
        raw_tools = [item for item in re.split(r"[\s,]+", value) if item]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        raw_tools = value
    else:
        raise ContractConfigError("allowed-tools must be a string or list of strings.", path=path)
    normalized: set[str] = set()
    for tool in raw_tools:
        normalized.add(tool.casefold())
        normalized.add(tool.split("(", 1)[0].casefold())
    return normalized


def _check_portability(value: Any, skill_dir: Path, path: Path) -> list[Finding]:
    if value is None:
        value = {"forbid_personal_paths": True}
    if not isinstance(value, dict):
        raise ContractConfigError("'portability' must be an object or false.", path=path)
    allowed = {
        "forbid_personal_paths",
        "allow_external_symlinks",
        "scan",
        "exclude",
        "allow",
    }
    unknown = set(value) - allowed
    if unknown:
        raise ContractConfigError(
            f"portability has unknown field(s): {', '.join(sorted(unknown))}.", path=path
        )
    forbid_paths = value.get("forbid_personal_paths", True)
    allow_external = value.get("allow_external_symlinks", False)
    if not isinstance(forbid_paths, bool) or not isinstance(allow_external, bool):
        raise ContractConfigError("portability boolean fields must be true or false.", path=path)
    scan_globs = value.get("scan")
    exclude_globs = value.get("exclude", [])
    allow_values = value.get("allow", [])
    if scan_globs is not None:
        scan_globs = _string_list(scan_globs, "portability.scan", path)
    exclude_globs = _optional_string_list(exclude_globs, "portability.exclude", path)
    allow_patterns = (
        _parse_pattern_list(allow_values, "portability.allow", path) if allow_values else []
    )

    findings: list[Finding] = []
    for candidate in _iter_portability_files(skill_dir, scan_globs, exclude_globs, path):
        display = _relative_display(candidate, skill_dir)
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            findings.append(
                Finding(
                    rule_id="portability.external_symlink",
                    kind="broken_symlink",
                    message="A scanned path cannot be resolved.",
                    file=display,
                )
            )
            continue
        if not _is_within(resolved, skill_dir) and not allow_external:
            findings.append(
                Finding(
                    rule_id="portability.external_symlink",
                    kind="external_symlink",
                    message="A scanned path resolves outside the skill directory.",
                    file=display,
                )
            )
            continue
        if candidate.is_symlink():
            try:
                target = candidate.resolve(strict=True)
            except OSError:
                findings.append(
                    Finding(
                        rule_id="portability.external_symlink",
                        kind="broken_symlink",
                        message="A scanned symlink is broken.",
                        file=display,
                    )
                )
                continue
            if not _is_within(target, skill_dir) and not allow_external:
                findings.append(
                    Finding(
                        rule_id="portability.external_symlink",
                        kind="external_symlink",
                        message="A symlink points outside the skill directory.",
                        file=display,
                    )
                )
                continue
        if not forbid_paths or candidate.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        try:
            text = candidate.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue
        for personal_pattern in PERSONAL_PATH_PATTERNS:
            for match in personal_pattern.finditer(text):
                line_start = text.rfind("\n", 0, match.start()) + 1
                line_end = text.find("\n", match.end())
                line_text = text[line_start:] if line_end < 0 else text[line_start:line_end]
                matched = match.group(0)
                if any(
                    _search_pattern(matched, allowed_pattern) is not None
                    or _search_pattern(line_text, allowed_pattern) is not None
                    for allowed_pattern in allow_patterns
                ):
                    continue
                findings.append(
                    Finding(
                        rule_id="portability.personal_paths",
                        kind="personal_absolute_path",
                        message="A user-specific absolute path was found.",
                        file=display,
                        line=_line_number(text, match.start()),
                    )
                )
    return findings


def _iter_portability_files(
    skill_dir: Path,
    scan_globs: list[str] | None,
    exclude_globs: list[str],
    contract_path: Path,
) -> Iterable[Path]:
    if scan_globs is None:
        candidates = skill_dir.rglob("*")
    else:
        for pattern in scan_globs:
            normalized = pattern.replace("\\", "/")
            posix_pattern = PurePosixPath(normalized)
            windows_pattern = PureWindowsPath(pattern)
            if (
                posix_pattern.is_absolute()
                or windows_pattern.is_absolute()
                or windows_pattern.drive
                or ".." in posix_pattern.parts
            ):
                raise ContractConfigError(
                    f"portability.scan pattern escapes its allowed directory: {pattern}",
                    path=contract_path,
                )
        candidates = (candidate for pattern in scan_globs for candidate in skill_dir.glob(pattern))
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen or not (candidate.is_file() or candidate.is_symlink()):
            continue
        seen.add(candidate)
        relative = _relative_display(candidate, skill_dir)
        if any(part in IGNORED_DIRECTORIES for part in Path(relative).parts):
            continue
        if any(
            candidate.match(pattern) or Path(relative).match(pattern) for pattern in exclude_globs
        ):
            continue
        yield candidate


def _string_list(value: Any, label: str, path: Path) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise ContractConfigError(f"{label} must be a non-empty list of strings.", path=path)
    return value


def _optional_string_list(value: Any, label: str, path: Path) -> list[str]:
    if value == []:
        return []
    return _string_list(value, label, path)


def _safe_join(root: Path, relative: str, label: str, contract_path: Path) -> Path:
    candidate_value = Path(relative)
    if candidate_value.is_absolute():
        raise ContractConfigError(f"{label} must be relative: {relative}", path=contract_path)
    candidate = (root / candidate_value).resolve()
    if not _is_within(candidate, root):
        raise ContractConfigError(
            f"{label} escapes its allowed directory: {relative}", path=contract_path
        )
    return candidate


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _display_path(path: Path, base: Path) -> str:
    try:
        relative = os.path.relpath(path, base)
    except ValueError:
        return path.name
    return Path(relative).as_posix()


def _relative_display(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1
