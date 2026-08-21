# Security policy

## Supported versions

Security fixes are provided for the latest tagged minor release. Before the first stable release, users should pin an exact tag and review changelog entries when upgrading.

## Private reporting

Use GitHub’s private vulnerability reporting form under the repository’s Security tab. Include a minimal synthetic reproduction when possible. Do not attach private `SKILL.md` files, credentials, customer data, or proprietary repositories.

If a report concerns accidental public exposure, identify the affected public file and the type of data without repeating the sensitive value.

## Scope

The checker reads local contract and skill files. It does not execute skill scripts, call an LLM, or access the network during a check. Findings intentionally omit matched source text.

Contracts do not enforce runtime agent behavior. Sandboxing, least-privilege tools, user approval gates, secret scanning, and audit logs remain necessary.
