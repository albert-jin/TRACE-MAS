# Contributing

Thank you for your interest in TRACE-MAS. This repository is a research
prototype, so contributions are most useful when they are focused, reproducible,
and easy to compare against the current experiment setup.

## Reporting Issues

When opening an issue, please include:

- the command you ran;
- the dataset and subset, if applicable;
- the model backend and model IDs;
- the Python version and operating system;
- the relevant log excerpt or stack trace;
- whether the problem is deterministic across repeated runs.

## Pull Requests

Before sending a pull request:

1. Fork the repository and work from the latest main branch.
2. Keep the change scoped to one fix or feature.
3. Avoid large formatting-only changes mixed with behavioral changes.
4. Run the smallest benchmark or unit check that exercises your change.
5. Update README or comments when the user-facing behavior changes.

For experiment changes, include the dataset, number of tasks, seed, model IDs,
and the before / after metrics.

## Code Style

- Prefer simple, explicit Python over clever abstractions.
- Keep benchmark adapters and method logic separated.
- Preserve compatibility with existing YAML configuration files unless the
  change explicitly migrates them.
- Do not commit API keys, local `.env` files, generated logs, or model outputs.

## License

By contributing, you agree that your contribution will be licensed under the
same license as the project. See [LICENSE](LICENSE).
