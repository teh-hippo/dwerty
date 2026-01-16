# AGENTS.md

_Last updated: January 2025_

## Purpose
This repo ships a firmware keymap for the Keychron V6 Max that implements Dvorak typing with Qwerty-position shortcuts (macOS-style \"Dvorak - QWERTY Command\"). Windows behavior is the priority; macOS support should be kept when it is low effort. Agents must keep changes small, tested, and well-documented.

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

## Project requirements (do not regress)
- **Target keyboard**: Keychron V6 Max (ANSI knob assumed unless user says ISO/JIS).
- **Custom layout**: Firmware-level Dvorak with Qwerty-position shortcuts; OS remains US Qwerty.
- **Platform priority**: Windows-first behavior; macOS support only when low effort.
- **Hardware parity**: Preserve all keys, encoder, media, and lighting effects.
- **UI editing**: Support post-flash UI-based editing (VIA and Keychron Launcher compatibility).
- **Testing**: Provide unit tests and integration tests (no-hardware when possible).
- **Code quality**: Enforce linting standards for Python, shell scripts, and C code.
- **Developer experience**: VS Code integration with tasks, debugging, and IntelliSense.
- **Containerization**: Streamlined Podman-based builds.
- **Workflow**: Provide rollback instructions and WSL-first workflow + flashing guidance.
- **CI/CD**: Keep CI workflows for tests and linting.
- **Maintainability**: Allow framework updates to latest versions when required.

## Approach and mindset
- Keep the tooling decision in [`README.md`](README.md) current; compare manufacturer recommendations vs tooling reality using primary sources.
- **QMK source** (last verified January 2025):
  - Prefer upstream QMK when it supports V6 Max; otherwise use Keychron QMK fork `Keychron/qmk_firmware` on `wireless_playground`.
  - Currently: upstream QMK lacks V6 Max support, so use Keychron fork.
- Use the layout macro from `keychron/v6_max/ansi_encoder` (`LAYOUT_ansi_109`).
- Maintain encoder (knob) and media key behavior from the stock keymap.
- Keep VIA enabled for post-flash UI editing and preserve Keychron Launcher compatibility.
- Keep the QMK repo clean; upgrade using [`./scripts/update_qmk.sh`](scripts/update_qmk.sh) and keep keymaps in this repo.
- Default update path stays on the current QMK branch unless `QMK_BRANCH` is set.

## Layout behavior
- Base layers are Dvorak (firmware-level).
- Assume the host OS remains in US Qwerty unless the user explicitly wants OS-level Dvorak.
- Windows-first: when Ctrl/Alt/GUI is held on Windows base layers, remap to Qwerty positions for shortcuts.
- macOS: default to Command-only (GUI) remap to mimic \"Dvorak - QWERTY Command\".
- Shift alone must NOT trigger Qwerty remap (unless user explicitly asks).
- Remap applies only to base layers.
- Always unregister remapped keys on release even if modifiers are released first.

## Files of record
- Keymap lives at `keymaps/keychron/v6_max/ansi_encoder/keymaps/dvorak_qwerty/`.
- Tests live in `tests/` and validate shortcut mappings.
- Scripts live in `scripts/` and handle install/build/flash scaffolding.

## Continuous improvement
- If assumptions are wrong (layout variant, OS expectations, shortcut behavior), update this file immediately with the corrected rule.
- If any manual step is error-prone, add a scripted helper and document it.
