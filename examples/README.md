# Examples

`safe-deploy` is a passing synthetic skill. `broken-deploy` is an intentional negative control that demonstrates a missing approval clause, an undeclared tool, a force-push instruction, and a synthetic user-specific path.

```bash
skill-contract check examples/safe-deploy
skill-contract check examples/broken-deploy
```

The second command must exit with code `1`. No example contacts a remote service or changes a repository.
