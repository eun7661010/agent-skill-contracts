# Contributing

Thank you for helping make Agent Skill regression checks easier to review and automate.

## Before opening a change

Search the issue tracker and describe the regression the change should prevent. For a new rule type, propose the contract shape before implementing a large patch.

Do not post real skill content when it contains private paths, credentials, customer data, unpublished instructions, or material that you cannot redistribute. Reduce the problem to a synthetic fixture.

## Development setup

```bash
git clone https://github.com/eun7661010/agent-skill-contracts.git
cd agent-skill-contracts
uv sync --extra dev
uv run ruff check .
uv run pytest --cov=agent_skill_contracts
uv run skill-contract check examples/safe-deploy
```

Python’s standard `venv` and `pip install -e ".[dev]"` also work.

## Pull requests

- Keep a pull request focused on one behavior.
- Add a passing case, an expected failure, malformed input coverage, and CLI output coverage when relevant.
- Keep findings free of source excerpts and matched secret-looking values.
- Update `schema/skill-contract.schema.json`, English documentation, and Korean documentation together when the public schema changes.
- Explain user-visible compatibility changes in `CHANGELOG.md`.

Maintainers may ask to split a large change when separate parts can be reviewed independently.

## Commit messages

Use a short imperative summary such as `Add SARIF result model` or `Clarify reference path errors`. Do not include private issue descriptions or local paths in commits.

## Reporting security issues

Follow [SECURITY.md](SECURITY.md). Do not open a public issue for a vulnerability or accidental data exposure.
