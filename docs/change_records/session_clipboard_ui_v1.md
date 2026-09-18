# Session Clipboard UI v1 -- Change Record

## 1. Record Identity

| Field | Value |
| --- | --- |
| Target repository | `smter6626/live_subtitle_generator` |
| Feature branch | `codex/session-clipboard-ui-v1` |
| Authorized baseline | `multiLanguage_v1` at `1e0cdd9fda1870a8277a553c3f7af7cc67480fe9` |
| Implementation commit | `cb4261825b7d51d3ec33a97e083683c50e6b9e82` |
| Status | Code, deterministic tests, independent review, and Human functional black-box accepted |
| Integration state | Feature branch pushed; not merged, tagged, or released by this record |

本记录是目标仓库内的维护摘要。完整 1PCloop 治理和运行 evidence 继续保存在 `smter6626/framework-loop`，不在两个仓库之间复制可变 Runtime。

## 2. User-Visible Behavior

实现提交增加并冻结以下行为：

1. `复制 Clean TXT 路径` / `Copy Clean TXT Path` 使用 Qt clipboard 复制当前 Session `clean.txt` 的绝对路径。没有有效 Session 时不改剪贴板；Stop 后仍可复制；新 Session 绑定新路径；该操作不改变文本复制断点。
2. 成功创建新 Session 时清空 Clean/Raw 显示、行数、queue 显示和文本复制断点。Stop 不清空；Session 建立前的 Start failure 不清空；历史 Session 文件不被移动或改写。
3. `复制新增 Clean 文本` / `Copy New Clean Text` 首次复制当前显示的全部 Clean 文本列，之后只复制上次成功写入剪贴板后新增的行。多行用换行连接；不包含 timestamp、Raw、日志或未显示的文件内容；无新行或 clipboard write failure 时不推进断点。
4. 中文界面的 UI language label 是精确字符串 `语言/Language`。音频/原文语言控件保持独立；新增按钮随中英文切换立即更新。

## 3. Session Ownership and Safety Boundary

Controller 为每个成功创建的 Session 分配随机 `session_id` 和单调递增的 `session_generation`。Engine callback 捕获这组 owner identity，并在改变 controller state 或继续向 UI 发 event 前拒绝旧 owner。

Qt signal 可能在队列中延迟，因此 `MainWindow.handle_event()` 再次校验相同 owner identity。两层检查共同防止上一 Session 的迟到 transcript、state 或 error event 污染新 Session 显示。

新 Session 清屏由有效且 generation 更高的 `session` event 驱动，而不是由按钮点击预先清屏。因此 Start 在 Session 创建前失败时，上一 Session 的可见内容和最后有效路径仍被保留。

## 4. Changed Source Surface

实现 commit 修改以下文件：

- `ui_app.py`
- `transcription_controller.py`
- `testCodes/test_session_clipboard_ui.py`
- `testCodes/test_ui_language.py`
- `README.md`
- `README.zh-CN.md`

Streaming backend、Whisper Runtime/model pin、转录和语言识别算法没有改变。

## 5. Validation Summary

Executor validation：

- Focused session clipboard UI: 9/9 PASS
- Related UI/output/language tests: 36/36 PASS
- Full unittest discovery: 117/117 PASS
- Standalone UI support checks: 22 PASS
- Python compile/import and Git diff checks: PASS

Independent Reviewer validation：

- Focused/related rerun: 20/20 PASS
- Full unittest discovery: 117/117 PASS
- Standalone UI support checks: 22 PASS
- Commit ancestry、changed-path scope、clean worktree 和 evidence identity: PASS
- Verdict: `ACCEPT`

Human-facing final review：

- Additional focused UI/language rerun: 15/15 PASS
- 1PCloop `status` / `inspect` and target evidence: PASS
- Human Owner real-function black-box: PASS；本轮功能实现无问题

自动测试使用 offscreen Qt 和 simulated/fake event boundary；它们没有被描述成真实音频黑盒。最终功能黑盒结论来自 Human Owner。

## 6. Known Follow-Up

Human black-box 同时发现主窗口纵向内容过长，会超出可用窗口范围。这是独立 UI layout defect，不反向否定本记录中的 clipboard/session 功能验收。

建议后续独立任务：

- 根据 macOS available screen geometry 限制初始和最小窗口尺寸；
- 在合适的控制区域增加滚轮、触控板和键盘可达的垂直滚动；
- 避免 transcript table 自身滚动与外层滚动形成不清晰的嵌套行为；
- 不以单纯缩小字体作为唯一修复；
- 回归本记录定义的 session ownership 和 clipboard 语义。

## 7. Cross-Repository Provenance

| Evidence | Identity |
| --- | --- |
| 1PCloop workload | `whisper_session_ui_v1` |
| 1PCloop run | `20260918T125410Z-30917` |
| Workload Static SHA-256 | `a361cf58b123db786505e12daec1673b39be5b1114d49b62d7b5779fffcc6d08` |
| Tracked evidence summary SHA-256 | `6e87bfa7dc506e986e4652c56ffd564a575623feabc339062fcd1ec9b4359cc0` |
| Framework evidence commit | `46461ad0073bdaae8ef32815a31778857fd35933` |
| Human closure commit | `efb7e1fd04a60b406c2fd7b59957c1797dcd990e` |

完整 raw evidence 可能包含本机路径、process metadata 和 Agent payload，因此不复制到目标仓库。需要过程级审计时，应在 framework commit 和 run ID 对应的权威记录中完成；日常维护以本记录和目标 source/tests 为入口。
