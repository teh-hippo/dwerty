# PLAN

## How to use this plan
- Keep statuses current as work proceeds (Not Started / In Progress / Done).
- Only one step should be In Progress at a time.
- When a step is Done, note any follow-up adjustments needed.

## Plan
1. **Docs reset + decision record** (Done)
   - Remove `APPROACH.md` and replace with `EVALUATION.md`.
   - Align `AGENTS.md` and `README.md` references to the new evaluation.

2. **Firmware behavior + UI editing support** (Done)
   - Implement Windows-first Dvorak-Qwerty shortcut behavior and Mac Command-only behavior.
   - Enable VIA for post-flash UI editing and keep Keychron Launcher compatibility.
   - Update unit tests for new modifier rules.
   - Refresh `README.md` with Windows-first guidance, WSL-first workflow, and rollback steps.

3. **Integration tests + scripts** (Done)
   - Add a host-side integration simulation for modifier remap sequences.
   - Add an optional QMK build check script (no hardware required).
   - Document integration test scope and limitations.

4. **CI workflow** (Done)
   - Add GitHub Actions to run unit + integration tests.

5. **Requirements alignment** (Done)
   - Put project requirements in `README.md` and `AGENTS.md`.
   - Separate project requirements vs agent mindset in `AGENTS.md`.

6. **Evaluation audit + consolidation** (Done)
   - Perform the tooling/framework audit with sources.
   - Consolidate findings into `README.md` and remove `EVALUATION.md`.

7. **Integration test plan + expanded vectors** (Done)
   - Add `docs/INTEGRATION_TESTING.md` to document phases and constraints.
   - Expand integration simulation coverage (shift-only, alt/gui, layer presence).

8. **Temporarily disable CI workflows** (Done)
   - Keep GitHub Actions disabled until final enablement pass.

9. **Shortcut vector integration checks** (Done)
   - Add common Windows shortcut vectors to simulation tests.
   - Ensure unmapped keys still pass through with modifiers.

10. **UAT workflow docs (WSL + usbipd)** (Done)
    - Add manual smoke test steps to `README.md`.
    - Add detailed UAT checklist in `docs/INTEGRATION_TESTING.md`.

## Review notes
- Windows behavior is the priority; macOS support should be minimal and Command-based.
- Firmware assumes OS layout stays US Qwerty; OS-level Dvorak would double-map.
- Qwerty shortcut remap is disabled on Fn layers by design; adjust only if requested.
