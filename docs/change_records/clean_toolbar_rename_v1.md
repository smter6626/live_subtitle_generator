# Clean toolbar and rename v1 — Change Record

## Scope

Branch: `codex/clean-toolbar-rename-v1`. Parent baseline: `569e5c551c101811ed80fca23bd5708d6ac880cf`. Status: awaiting independent review and Human validation.

Rename Clean TXT and Copy New Text are in the Clean toolbar, left of Jump to Live. Reveal Clean and Copy Clean Path share a row in the 310px controls column. Raw and Logs have no Clean actions. The dialog edits a stem with a separate fixed `.txt` label. All labels, tooltips, and feedback use the live Chinese/English language lookup.

## File and ownership semantics

The UI passes its Session ID and generation to the controller. The controller checks these against its current Session, then calls the store. The store validates the stem before filesystem work. Its Clean lock serializes append, rename, and close; Stop does not hold the controller session lock while waiting for workers. The store verifies the owned directory and current source identity and uses `renameatx_np(RENAME_EXCL)` on macOS or `renameat2(RENAME_NOREPLACE)` on Linux with a directory descriptor. No copy, link, or overwriting fallback is used. Unsupported systems fail closed.

Success changes the store and UI path only after the destination is verified as the regular file held by the Clean writer. The open writer continues on the same inode. Stop then rename and repeated rename work. A later Session creates a new `clean.txt`. Rename does not change displayed rows, counts, scroll, or the incremental clipboard cursor, and rename errors do not put the engine in ERROR.

After the no-replace call, the store rechecks the writer identity. If an external operation moves the original file to another `.txt` path in the same Session and places a decoy at the destination, the store finds the original inode and reports an ambiguous rename rather than success. Finder, Copy Clean Path, and the next rename request the current verified path through the controller at use time. They never use the UI path cache alone. A path that cannot be verified is cleared; Finder and path copy do nothing, preserving the clipboard.

## Failure matrix

| Case | Result |
| --- | --- |
| Cancel dialog | No operation or path change |
| Empty, whitespace, dot names, separators, controls, `.txt` suffix | Rejected before filesystem work |
| Missing, symlink, non-regular, or wrong-identity source; replaced Session directory | Rejected; store path unchanged |
| Existing or symlink destination; destination created concurrently | Atomic no-replace rejects collision; existing target preserved |
| Permission/I/O failure or missing primitive before the no-replace call | Localized feedback; current verified path remains usable |
| Destination replaced, removed, or made a symlink after the call | Reconcile to the writer inode at a different Session `.txt` path when one can be verified; report ambiguity, never publish the replacement |
| Original inode cannot be located in the Session or verification I/O fails throughout | Fail closed with no usable Clean path; further path actions do nothing until a verified path is found |
| Stale Session ID/generation | Rejected before store mutation |

## Verification and limits

Focused tests: `testCodes/test_clean_rename.py`, `testCodes/test_session_clipboard_ui.py`, `testCodes/test_window_layout.py`. Full discovery, compile/import, and `git diff --check` are required before the implementation commit. A file moved outside the Session, removed entirely, or made unreadable cannot be mapped back to an absolute Session path from the open writer alone; resolving the original AC-07 valid-path expectation in that external-mutation case requires a Human decision. The future LLM design documents still assume a fixed `clean.txt` reader; a separate reader migration is required. Real microphone, Finder, and macOS clipboard behavior remain for the Human gate. This record does not claim acceptance.
