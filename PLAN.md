# PLAN

## How to use this plan
- Keep statuses current as work proceeds (Not Started / In Progress / Done).
- Only one step should be In Progress at a time.
- When a step is Done, note any follow-up adjustments needed.

## Plan
1. **Scaffold project docs and guardrails** (Done)
   - Create/maintain `AGENTS.md`, `README.md`, and this plan.
   - Record assumptions (ANSI knob, Qwerty shortcuts behavior).

2. **Implement keymap + shortcut remap** (Done)
   - Build Dvorak base for Mac/Win layers from the stock V6 Max keymap.
   - Add Qwerty-position shortcut remap when Ctrl/Alt/GUI is held.
   - Keep encoder/media behavior from stock keymap.

3. **Add tests and scripts** (Done)
   - Unit tests to validate shortcut mapping coverage.
   - Helper scripts for install/build/flash workflows.

4. **Document build/flash + device install** (Done)
   - Clear local build instructions.
   - Clear device flashing instructions, including reset steps and cable mode.

5. **Review + iterate** (Done)
   - Principal IC review of risks/edge cases.
   - If needed, iterate on mapping or docs.

6. **Finalize and push** (Done)
  - Run tests.
  - Commit and push to `origin`.

## Review notes (Principal IC)
- Confirm keyboard variant (ANSI knob vs ISO/JIS) before flashing.
- Firmware assumes OS layout stays US Qwerty; OS-level Dvorak would double-map.
- Qwerty shortcut remap is disabled on Fn layers by design; adjust if needed.
