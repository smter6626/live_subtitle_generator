# Clean full-text recovery R2 — Change Record

## Scope and status

Branch: `codex/clean-toolbar-rename-v1`. R2 baseline: `b62ef6947d6a634c56e695740e4ea446751e6c79`. Status: implemented for independent review; no acceptance is claimed.

R2 extends the existing Clean rename action only when a complete inspection of the verified original Session directory proves that the Clean writer inode has no regular `.txt` path there. It does not alter ASR/audio/model behavior, Raw or Logs, Session creation/numbering, displayed transcript rows, counts, scroll state, or the incremental copy cursor.

## Recovery and ownership semantics

`TranscriptStore` opens Clean read/write and treats the exact flushed UTF-8 bytes in that writer as the recovery source. Append, path inspection, snapshot, rename, recovery, writer replacement, and close share the Clean lock. `close()` preserves a trusted final byte snapshot, enabling recovery after Stop while that Store remains the controller's current Session.

Path inspection opens and verifies the original Session directory by device/inode and scans every `.txt` entry without following symlinks. A completed scan with no writer-inode match is reported distinctly as `source_unavailable`, but only after an exact snapshot is available. Directory replacement, `scandir`, entry-stat, flush, read, or identity failures remain uncertain and fail closed.

Recovery validates the requested stem, writes the complete snapshot to a Session-local exclusive temporary file, flushes it with `fsync`, verifies its bytes and inode, and publishes with the same OS atomic no-replace primitive used by rename. While active, the destination is reopened and reverified before the Store switches writers; later appends go only to that file. After Stop, the verified file remains closed. The externally moved original is never changed. Temporary/new entries are removed only after owned-inode verification on failure.

The controller requires the captured Session UUID and generation for recovery. A stale confirmation after a newer Session begins cannot inspect or mutate either Store.

## UI behavior

The stem dialog remains available when the last verified path is conclusively unavailable. The Chinese/English confirmation presents the old path only as an unavailable hint, describes complete-history creation and later active appends, and warns that No makes no change while an open handle alone does not guarantee a safe path or durable output after close/app exit. No/cancel is retryable. Uncertain states show a localized error and never show the recovery choice. Reveal Clean and Copy Clean Path continue to reverify at use time and leave Finder/clipboard untouched without a verified writer path.

## Failure matrix

| Case | Result |
| --- | --- |
| Existing file or symlink, including the attempted/old-path decoy | Atomic collision failure; target is not followed or overwritten |
| Session directory replaced or identity changed | Unsafe failure before creation |
| Scan, entry-stat, flush, read, permission, open, write, `fsync`, verification, or writer-switch failure | No success is reported; owned temporary/new entry is cleaned when still identifiable; active old writer remains usable |
| Append racing active recovery | Append waits on the Clean lock, then writes once to the verified new writer in order |
| No/cancel | No file or switch; active old handle can continue receiving appends; same-Session retry remains available |
| Stale Session ID/generation | Rejected by controller before Store inspection or mutation |
| Recovery after Stop | Uses the trusted pre-close snapshot and leaves the recovered file closed |
| Reveal/path copy with no verified path | Finder and clipboard remain unchanged; decoys are never exposed |

## Verification and limits

Deterministic tests use only auto-cleaned temporary fictional Sessions. `testCodes/test_clean_rename.py` covers Unicode/timestamp byte identity, external move/unlink and decoys, active serialization, post-Stop recovery, No/retry, stale confirmation, collision/symlink/directory replacement, uncertain inspection/read/flush, copy/switch/write/`fsync`/open/verification failures, bilingual text, Finder/clipboard fail-closed behavior, and the prior rename/layout/cursor ownership contracts. Focused and full-suite command results and the descendant commit SHA are reported in the Executor receipt.

Real microphone capture, Finder presentation, macOS clipboard integration, and destructive external filesystem races remain Human/real-macOS validation boundaries.
