# AGENTS.md

_Last updated: January 2025_

See [`README.md`](README.md) for project behavior, layout rules, and tooling decisions.

## Operating rules
- Work in small, reviewable steps. Prefer tidy diffs and minimal churn.
- Update [`README.md`](README.md) whenever behavior, setup, or flashing steps change.
- Run available tests after each change when possible ([`./scripts/test.sh`](scripts/test.sh)).
- Run linting before committing code ([`./scripts/lint.sh`](scripts/lint.sh)).
- Keep scripts idempotent and safe; avoid destructive commands.
- After tests pass, commit and push to `origin`.
- Prefer Podman-based workflows for containerized builds; avoid Docker usage in docs or scripts.
- When documenting or validating Keychron Launcher steps, specify Chrome/Edge/Opera (latest) as the supported browsers.
- Treat Keychron Launcher as the official **stock firmware** path; use QMK Toolbox/CLI for custom `.bin` flashing.
- Use VS Code tasks (defined in [`.vscode/tasks.json`](.vscode/tasks.json)) when available for build/test/lint operations.

## Continuous improvement
- If assumptions are wrong (layout variant, OS expectations, shortcut behavior), update this file immediately with the corrected rule.
- If any manual step is error-prone, add a scripted helper and document it.
