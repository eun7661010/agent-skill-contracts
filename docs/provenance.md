# Provenance and redistribution notes

The implementation in this repository was written for `agent-skill-contracts`. It does not contain copied source files, Git history, fixtures, templates, or documentation from a private project.

The design was informed by a common maintenance problem: a valid `SKILL.md` can still lose a repository-specific approval boundary or required reference during an edit. The public tools listed in the README helped define the project boundary. Their source code was not copied into this implementation.

## Runtime dependency

| Dependency | Purpose | License |
| --- | --- | --- |
| [PyYAML](https://github.com/yaml/pyyaml) | Parse YAML contracts and frontmatter | MIT |

Development and CI dependencies are recorded in `pyproject.toml` and locked in `uv.lock`. They are not bundled into the source distribution or wheel.

## Fixtures and examples

Every skill, path, policy, and deployment target under `examples/` and `tests/` is synthetic. The broken example intentionally contains a fictional home path and an unsafe command so the negative control can prove that the checker fails.

If a future contribution adapts external code or an asset, record its source, version, license, and modifications here and in `NOTICE` before merging it.
