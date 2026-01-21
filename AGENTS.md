# AGENTS.md

See [`README.md`](README.md) for project details.

## Operating Rules

- Work in small, reviewable steps with tidy diffs
- Update [`README.md`](README.md) when behavior/setup/flashing changes
- Run tests after changes: [`./scripts/test.sh`](scripts/test.sh)
- Run lint before commits: [`./scripts/lint.sh`](scripts/lint.sh)
- Keep scripts idempotent and safe
- After tests pass, commit and push to `origin`
- Use Podman-based workflows for containerized builds
- Specify Chrome/Edge/Opera (latest) as supported browsers for Keychron Launcher
- Keychron Launcher = official stock firmware; QMK Toolbox/CLI = custom `.bin` flashing
- Use VS Code tasks from [`.vscode/tasks.json`](.vscode/tasks.json) when available
