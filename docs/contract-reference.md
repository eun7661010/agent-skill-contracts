# Contract reference

This document describes contract schema version `1`. The JSON Schema at `schema/skill-contract.schema.json` supports editor validation, while the CLI remains the authoritative implementation.

## Discovery and path rules

`skill-contract check <path>` accepts one contract file or a directory. Directory checks recursively discover `skill-contract.yaml`, `skill-contract.yml`, and `skill-contract.json` while skipping common dependency and cache directories.

Every path in a contract is relative. It is resolved from the contract directory and must stay below that directory. Rule targets, required files, reference files, and reference source files must also remain inside the selected skill directory.

## Top-level fields

### `version`

Required. The only supported value is `1`.

### `skill`

Optional. A relative path from the contract directory to the skill directory. The default is `.`.

### `rules`

Optional list of text assertions. Each rule supports:

- `id`: required stable identifier matching `^[a-z0-9][a-z0-9._-]*$`
- `description`: optional human explanation
- `target`: relative text file, defaulting to `SKILL.md`
- `require.all`: every listed pattern must match
- `require.any`: at least one listed pattern must match
- `forbid`: no listed pattern may match

A pattern may be a string shorthand or an object:

```yaml
rules:
  - id: approval-gate
    require:
      all:
        - explicit approval
        - regex: stop\s+when\s+approval\s+is\s+absent
          case_sensitive: false
```

String patterns and regular expressions are case-insensitive by default. Set `case_sensitive: true` on an object pattern when casing is part of the contract.

### `files.required`

Lists files that must exist inside the skill directory.

```yaml
files:
  required:
    - scripts/check.py
    - references/safety.md
```

### `references.required`

Each entry must exist and must be mentioned by its source file. A string entry uses `SKILL.md` as the source. An object may select another source:

```yaml
references:
  required:
    - references/safety.md
    - path: scripts/validate.py
      mentioned_in: references/implementation.md
```

The mention check is literal and path-separator tolerant. It does not infer semantic relationships.

### `frontmatter`

Checks required metadata fields and declared tools in `SKILL.md`:

```yaml
frontmatter:
  required_fields: [name, description]
  required_tools: [Read, Bash]
```

The tool check accepts `allowed-tools` or `allowed_tools`, as a whitespace-separated string, comma-separated string, or YAML list. A declaration such as `Bash(git:*)` also satisfies a requirement for `Bash`.

### `portability`

Portability checks are enabled by default. Set `portability: false` to disable them for a contract.

```yaml
portability:
  forbid_personal_paths: true
  allow_external_symlinks: false
  scan:
    - SKILL.md
    - references/**/*.md
    - scripts/**/*
  exclude:
    - references/generated/**
  allow:
    - regex: /home/example-user/\S+
```

`forbid_personal_paths` detects user-specific paths below Windows `Users`, macOS `Users`, and Linux `home`. Findings do not echo the matched path, which reduces accidental disclosure in CI logs.

Use `allow` only for reviewed synthetic negative fixtures. Broad allow patterns can hide real portability problems.

External symlinks are rejected by default because they make a skill depend on files that are absent from a fresh clone. Broken symlinks are always reported.

## Extension fields

Unknown fields fail closed. Top-level and rule-level fields beginning with `x-` are reserved for local metadata and ignored by the CLI.

## Exit codes

| Code | Meaning |
| ---: | --- |
| `0` | Every discovered contract passed. |
| `1` | At least one valid contract found a behavioral violation. |
| `2` | The command, path, syntax, or contract configuration was invalid. |

## Output formats

`text` is intended for terminals. `json` is stable machine-readable output with schema version `1`. `github` emits workflow annotations without including matched source text.
