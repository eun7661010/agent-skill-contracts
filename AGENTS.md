# Repository guidance for coding agents

Keep the checker deterministic, offline, and safe to run on untrusted skill repositories.

- Do not add LLM or network calls to the default check path.
- Never print matched source lines or secret-looking values in findings.
- Resolve every contract path below its declared root before reading it.
- Use only synthetic names, paths, credentials, and documents in tests and examples.
- Add a positive case, negative control, malformed-input case, and output assertion for new rule types.
- Run `uv run --extra dev ruff check .` and `uv run --extra dev pytest --cov=agent_skill_contracts` before reporting completion.
- Keep README.md, README.ko.md, the contract references, JSON Schema, and CLI behavior aligned.
