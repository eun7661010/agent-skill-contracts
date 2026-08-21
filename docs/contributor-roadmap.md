# Contributor roadmap

The following tasks are intentionally bounded starting points. Please open or claim an issue before implementing a larger item.

## Good first issues

1. Add concise examples for `allowed-tools` values used by another Agent Skills host.
2. Improve an error message that currently requires reading the contract reference.
3. Add a synthetic fixture for a path format that the portability checker should accept or reject.
4. Add editor setup instructions for associating `skill-contract.yaml` with the bundled JSON Schema.
5. Add a pre-commit configuration example and test it in a temporary repository.

## Help wanted

1. Design SARIF output without exposing matched source content.
2. Add contract inheritance while keeping path resolution explicit and cycle-free.
3. Add optional line-aware frontmatter findings.
4. Package standalone binaries and document reproducible builds.
5. Compare behavior on case-sensitive and case-insensitive file systems.

## Design constraints

- Checks must remain deterministic and work without a network connection.
- A finding must not print the matched source line by default.
- Contract paths must not escape the declared root.
- New fixtures must be synthetic.
- New rule types need positive, negative, malformed-input, and CLI output tests.
