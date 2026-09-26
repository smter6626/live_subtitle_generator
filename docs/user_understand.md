# user_understand.md

最后更新：2026-09-25

这份文档用于快速恢复项目上下文。当前源码行为以代码、测试和 [`repo_map.md`](repo_map.md) 为准；正式下载版边界以根目录双语 README 和 Release 页面为准。

## 1. 一句话理解项目

Classroom Live Transcriber 是一个面向 macOS Apple Silicon 的本地近实时课堂转写工具：麦克风音频被切成重叠 chunk，由 `whisper.cpp` + Metal 在本机转写，PySide6 UI 实时显示结果，每次录音保存独立 Session。

```text
麦克风
-> 音频 chunk
-> 本地 whisper.cpp
-> Raw/Clean UI
-> Session 文件
```

当前转写主链路不依赖云端 LLM。

## 2. Release 与 feature branch

- 当前正式 GitHub Release 是 `1.0.0`。
- Release 1.0.0 是 macOS Apple Silicon 下载版，尚未 notarize，也没有 LLM summary。
- 当前开发分支是 `codex/clean-toolbar-rename-v1`。
- 窗口高度约束、Session 显示重置/增量复制、Clean 工具栏、重命名和全文恢复已经在该 feature branch 实现并通过自动、独立和 Human macOS 验收。
- 这些 feature-branch 能力尚未 merge、tag 或打包到 1.0.0；不能把 README 中的开发分支功能误认为下载版已有功能。

## 3. 当前主链路和 ownership

```text
ui_app.py
-> TranscriptionController
-> TranscriptionEngine
-> WhisperCppBackend
-> TranscriptStore
```

- `ui_app.py` 管理界面、对话框和当前 Session projection。
- `transcription_controller.py` 管理状态机、当前 Session UUID + generation，并拒绝旧 Session 操作。
- `transcription_engine.py` 管理录音、chunk 调度、worker、raw/clean 事件和 Stop drain。
- `transcript_store.py` 管理 Session 目录、文件 writer、Clean 身份、重命名、恢复和 close snapshot。
- `stream_transcribe.py` 包含 whisper.cpp backend helper 与 dedup helper。

新 Session 创建后，UI 清空之前显示的 Clean/Raw 行、计数和复制断点。Stop 只结束当前 Session，不清空已经显示的内容；Start 如果在新 Session 创建前失败，也保留之前显示。

## 4. 用户当前可见能力

- Start/Stop 本地转写；Stop 等待已提交音频处理结束。
- Clean Transcript、Raw Transcript 和 Logs 三个视图。
- UI 语言为中文或 English。
- 音频原始语言支持 English、Chinese、Japanese、French、Spanish、German、Korean 和 Auto Detect；UI 语言与 ASR 语言互不影响。
- Beam 为 `3-8`，默认 `5`。
- Model Manager 支持下载、完整性验证、导入和选择模型。
- Output Location 可配置。
- 主窗口高度受当前屏幕可用区域限制；左侧控制栏独立滚动，右侧三个视图各自滚动。
- Clean 工具栏支持 Rename Clean TXT、Copy New Text、Jump to Live。
- 左侧同一行提供 Reveal Clean 和 Copy Clean Path。

## 5. Session 文件和当前 Clean artifact

每次 Start 初始创建：

```text
outputs/YYYY-MM-DD_HH-MM-SS/
  raw.txt
  clean.txt
  session.log
  config.json
```

`raw.txt` 保存后端原始 timestamp evidence。Clean transcript 经过保守边界去重和有限高置信过滤，不是语义改写。

`clean.txt` 现在只是当前 Clean artifact 的初始文件名：

- 普通 Rename 可将它改成用户输入的 `<stem>.txt`。
- 用户只能输入 stem，`.txt` 后缀由 App 固定。
- 重命名不会覆盖已有文件，也不会通过 copy/link fallback 冒充 rename。
- 录制中和 Stop 后都可重命名。
- 新 Session 创建后，UI 操作对象切换到新 Session 的初始 `clean.txt`。

Reveal Clean 和 Copy Clean Path 每次使用都会重新核对 Session 目录和 writer inode。验证失败时不会打开 Finder，也不会修改剪贴板。

## 6. Clean 路径消失时的全文恢复

App 只有在完整检查证明当前 writer inode 在经过验证的原 Session 目录中没有普通 `.txt` 路径时，才显示恢复确认。

- Yes：无覆盖创建用户指定的 `<stem>.txt`，内容是切换前全部精确 Clean bytes。
- 录制仍在进行时，后续 append 只进入新 writer。
- Stop 后恢复使用 close 前保存的可信 snapshot。
- No/cancel：不创建、不切换，操作以后可以重试。
- No 后 open writer 仍可能继续接收内容，但文件句柄不等于安全、持久、可重新定位的路径；关闭文件或退出 App 后不能保证仍可找回。

以下情况不会被当成“文件已消失”：

- 权限或 I/O 失败
- Session 目录身份不一致
- entry stat/读取不确定
- symlink、目录或 decoy
- 事务中 Session pathname 或 destination 被替换

这些状态都 fail closed。目标已存在时也不会覆盖。

App 内部 append、snapshot、rename、recovery、writer switch 和 close 由同一把锁串行化。但它没有跨程序文件锁；外部无锁进程仍可能在最后检查后继续修改 Session。

## 7. Copy New Text 语义

- 第一次成功复制当前 UI 中全部 Clean 行。
- 后续只复制上次成功复制之后新增的行。
- 没有新行时不修改剪贴板。
- rename/recovery 不改变复制断点。
- 新 Session 将复制断点重置为 0。
- 复制来源是当前 UI Clean 行，不是重新读取磁盘文件。

## 8. 已知技术边界

- 正式 Release 仅验证 Apple Silicon；没有 Intel Mac 或 Windows 下载版。
- 当前 inference 仍按 chunk 调用 whisper.cpp CLI，不是零延迟。
- 没有正式 Developer ID notarization。
- 没有 LLM summary、语义纠错或跨 Session RAG。
- 没有跨 App restart 的持久 current-Clean locator/manifest。
- settings 仍是简单 JSON，没有 schema migration。
- `stream_transcribe.py` 长期看职责偏多。

## 9. 未来 LLM 工作的首要 blocker

旧设计把 `session_dir/clean.txt` 当成永久固定输入。当前 feature branch 已使该假设失效：完成后的 current Clean 可能是用户命名 `.txt`，也可能来自全文恢复。

任何 LLM、Session Browser 或 Search 实现之前，都必须先完成 trusted current-Clean resolver：

1. 用持久 locator/manifest 绑定 Session 与准确 current Clean artifact。
2. 普通 rename、active recovery 和 post-Stop recovery 必须事务式更新 locator。
3. App restart 后仍能验证普通文件类型、Session ownership 和身份。
4. 不能扫描目录后选择任意 `.txt`，不能信任同名 decoy 或 symlink。
5. 旧 Session 无法唯一迁移时必须报告 unavailable/ambiguous，并阻止 LLM 调用。

详细设计边界见 [`LLM_POSTPROCESSING_DESIGN.md`](LLM_POSTPROCESSING_DESIGN.md) 和 [`LLMsteps.md`](LLMsteps.md)。resolver 尚未实现，不能在文档或代码中把它写成现有能力。

## 10. LLM 后处理的保留方向

resolver gate 完成后，LLM 第一阶段仍应是 after-stop sidecar：

- 只读 resolver 验证过的 current Clean artifact。
- 默认生成中文 summary 和结构化 JSON。
- 输出写入 `session_dir/llm/`。
- API key 不进入仓库、settings、Session config 或日志。
- 单元测试使用 mock provider，不调用真实 API。
- LLM 失败不影响 Start/Stop、麦克风释放、raw/Clean writer 或 UI 主线程。
- 不改写 raw 或当前 Clean artifact。

每分钟翻译仍是后续可选 sidecar，不属于第一阶段。

## 11. 回来继续开发时先看

1. 用户使用和 Release 边界：根目录 [`README.md`](../README.md) / [`README.zh-CN.md`](../README.zh-CN.md)。
2. 当前模块 ownership 和数据流：[`repo_map.md`](repo_map.md)。
3. 工程实现细节：[`工程细节.md`](工程细节.md)。
4. LLM gate 和未来工作：[`LLM_POSTPROCESSING_DESIGN.md`](LLM_POSTPROCESSING_DESIGN.md) / [`LLMsteps.md`](LLMsteps.md)。
5. 打包和发布：根目录 [`PACKAGING.md`](../PACKAGING.md) 及 deployment 文档。

不要从已经删除的逐任务 change record 恢复当前产品事实。详细 1PCloop verdict、REJECT -> REPAIR 过程和 raw evidence 保留在 framework-loop；target 仓库只保留稳定用户行为和当前技术合同。
