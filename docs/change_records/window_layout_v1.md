# Window Layout v1 — Change Record

## Identity and status

| Field | Value |
| --- | --- |
| Target branch | `codex/bounded-scrollable-main-window-v1` |
| Fixed parent baseline | `fb7e38e4248b1b6fcf58a14193dbfe9315f90f34` |
| Implementation | This record's containing commit (source, tests, and documentation are one commit) |
| Status | AWAITING_REVIEW — independent review and real macOS visual/trackpad Human Gate remain required |

## Behavior and ownership

`MainWindow` obtains the effective Qt screen's available geometry through an injectable provider. It applies a client-height ceiling that accounts for observed frame overhead when the window is built, first shown, moved to another effective screen, or receives an available-screen/geometry change. The root layout does not let a content-derived minimum height override that ceiling; users retain ordinary resizing up to the current screen limit.

Only the left Controls/Session column owns the new vertical scroll area. The status strip remains above it, outside the scroll content. Clean and Raw remain `QTableWidget` scrolling surfaces and Logs remains a `QPlainTextEdit` scrolling surface; there is no outer whole-window scroll area or global wheel handler. Qt focus traversal can scroll focused controls into view, so off-viewport controls remain reachable with Tab and Shift-Tab.

All existing control, session, clipboard, language, output, model, Start/Stop, event, and shutdown object references and behaviors are retained. No ASR backend, controller, store, settings schema, model/runtime manifest, packaging Runtime, or evidence-file semantics changed.

## Verification scope

`testCodes/test_window_layout.py` is the focused offscreen Qt regression suite. It exercises injected normal, short, and very short available geometries through the actual show/layout path; resize from normal to short through the production available-geometry handler; the effective-screen handler; left scrollbar/mouse-wheel and Tab/Shift-Tab reachability; independent Clean/Raw/Logs wheel ownership; and Chinese/English retranslation while bounded.

The executor also runs the existing session clipboard, UI language, output root, model-manager UI, full discovery, standalone UI-support, compilation/import, and diff checks. Raw command logs and the generated geometry/scroll/focus matrix stay outside Git and are reported by path and SHA-256 in the execution receipt.

## Human Gate

Offscreen Qt cannot establish real macOS title-bar placement, multi-display transitions, scrollbar appearance, or mouse/trackpad feel. A Human must launch the source UI with `.venv/bin/python ui_app.py` and verify initial screen bounds, short-height access by scrollbar/mouse/trackpad/keyboard, independent Clean/Raw/Logs scrolling, bilingual switching, resize behavior, and the existing session/clipboard actions before acceptance. This record does not claim ACCEPT.
