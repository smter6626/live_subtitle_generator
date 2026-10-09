# Classroom Transcriber 1.1.0 / 课堂实时转写 1.1.0

Tag/version: `1.1.0`. Asset: `ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip`, containing `ClassroomTranscriber.app`, from `smter6626/live_subtitle_generator`. This document describes the version's changes and installation requirements; it is not evidence that any particular ZIP has been built, accepted or published.

## English

Version 1.1.0 adds separate Original Language choices for English, Chinese, Japanese, French, Spanish, German, Korean and Auto Detect audio. English-only `.en` models accept English only; all other choices, including Auto Detect, require a multilingual model. Interface Language remains independently selectable as Chinese or English.

Starting a new Session clears the Clean/Raw display and resets incremental Copy New Text. Reveal Clean and Copy Clean Path verify the current Session writer before acting. The window stays within the available screen height, with independently scrolling controls, transcripts and logs. The Clean toolbar provides no-clobber Rename Clean TXT while recording and after Stop. R2 full-history recovery offers Yes/No only when the writer conclusively has no regular `.txt` path in its verified original Session: Yes creates the complete history without overwriting and switches future appends; No or cancel creates and switches nothing. Uncertain inspection stops without offering recovery.

The packaged icon, model-selection confirmation feedback and visible model-download activity feedback are retained 1.0 functionality, not new 1.1.0 additions.

Whisper models remain external and are not included. The macOS distribution uses ad-hoc signing and is not notarized.

To install a verified ZIP, extract it in Finder and double-click `ClassroomTranscriber.app`. If macOS cannot verify it, close the warning, use System Settings -> Privacy & Security -> Open Anyway, authenticate if requested, and open it again. Release-owner Human review must use the exact retained extraction bound to the ZIP, not a source-run or older App.

Historical 1.0.0 testing on M4 Max and M5 with macOS 27 Beta does not accept new 1.1.0 artifact bytes. Other Apple Silicon generations and older macOS remain unverified; no minimum macOS is established. The language menu does not claim real-audio coverage of every language/model combination. Every published 1.1.0 artifact must be bound to its exact integrated source, fresh build, automatic package verification and exact-artifact Human review; this document alone supplies none of those acceptance facts.

## 中文

1.1.0 新增独立 Original Language 选择：英语、中文、日语、法语、西班牙语、德语、韩语和自动检测。英语专用 `.en` 模型只接受英语；其他选项（含自动检测）需要多语言模型。Interface Language 仍独立选择中文或 English。

新 Session 会清空 Clean/Raw 显示并重置“复制新增文本”的断点。“定位 Clean”和“复制 Clean 路径”先验证当前 Session writer。窗口高度受屏幕可用范围约束，控制栏、转写和日志各自滚动。Clean 工具栏支持录制中及 Stop 后无覆盖“重命名 Clean TXT”。R2 全文恢复只在完整检查确定 writer 于经过验证的原 Session 中没有普通 `.txt` 路径时提供“是/否”：是会无覆盖创建完整历史并切换后续追加；否或取消不创建、不切换。检查不确定时停止，不提供恢复。

应用图标、模型选择确认反馈及可见的模型下载活动反馈均为保留的 1.0 功能，不是 1.1.0 新增。

Whisper 模型仍为外部文件，不包含在 macOS 分发包中。macOS 分发使用 ad-hoc 签名，不进行公证。

安装已核验的 ZIP 时，在 Finder 解压并双击 `ClassroomTranscriber.app`。若 macOS 无法验证，关闭提示，通过“系统设置 -> 隐私与安全性 -> 仍要打开”按需认证，再次打开。Release Owner 人工验收必须使用与该 ZIP 绑定的精确保留解压 App，不能使用源码运行或旧 App。

1.0.0 曾在 macOS 27 Beta 的 M4 Max/M5 上测试，仅属历史证据，不接受新的 1.1.0 产物字节。其他 Apple Silicon 代际和更早 macOS 未验证，最低 macOS 未确定；语言菜单不代表每种语言/模型组合都经过实音频测试。每份正式发布的 1.1.0 产物都必须绑定精确集成源码、fresh build、自动验包及精确产物人工验收；本文自身不提供这些验收事实，也不证明任何具体 ZIP 已构建、接受或发布。
