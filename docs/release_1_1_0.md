# Classroom Transcriber 1.1.0 -- 发布与验证范围

- 发布日期: 2026-10-11。
- 正式版: [Classroom Transcriber 1.1.0](https://github.com/smter6626/live_subtitle_generator/releases/tag/1.1.0)，非预发布，作为最新正式版本。
- 下载: [macOS Apple Silicon ZIP](https://github.com/smter6626/live_subtitle_generator/releases/download/1.1.0/ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip)。
- Asset: `ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip`，48,307,378 字节。
- SHA-256: `fbe14de7d68c519ddb817ef1f45166f3e39a24f0a27d290cd82d9c2c20717bdb`。
- 构建源码及 tag peeled commit: `014a609fcc7ab26be8820f4399cdaa19225498e1`。
- Annotated tag object: `32b21b1b2f660d2315d60569cae94ecd5b3b440b`。
- Release ID: `409876735`；Asset ID: `631624978`。

## 本版主要变化

新增独立的音频语言选择、新 Session 清屏和复制断点重置、增量复制文本、当前 Clean 文件定位与路径复制、适应屏幕高度的窗口和独立滚动、双语 Clean 工具栏及无覆盖重命名。原 Session 中的 Clean 路径被确定移除时，可以选择从完整历史无覆盖恢复一个新 TXT，并切换后续追加。详细行为见中英 README 与 [本版说明](../RELEASE_NOTES_1.1.0.md)。

## 验证到了什么

固定集成源码通过 297 项 ResourceWarning-strict 测试；正式 fresh build 通过原 Runtime/App/provenance/ZIP 和解压验证，独立复核再次确认包身份及签名。Owner 实际使用该 ZIP 对应的保留解压 App，回报未发现异常，并明确允许发布。

一次 large-v3 英语真实转录约 25 分 26 秒，218 个音频块全部处理，Raw 568 行、Clean 514 行与日志一致，重新去重计算与 Clean 文件逐字节一致，停止时最后一段音频正常处理。没有原始音频真值，因此不声称每句话准确或没有漏识别；也不把输出文件检查当作全部交互的逐项测试。

发布使用同一个已验收 ZIP，先下载草稿资产比对，公开后再下载并核对字节数与 SHA-256；远端 tag、版本、标题、说明、唯一资产和 latest 状态同时核验。后续文档提交不修改 tag 或已发布包。

## 使用和剩余限制

- 下载、解压、打开 App 即可，不需要安装 Python/CMake/whisper-cli，也不需要修改 Homebrew 权限或用终端授权。
- 模型不内置，请通过 Model Manager 下载或导入。
- 仅 macOS Apple Silicon / arm64；最低 macOS 未确定，不承诺未验证的硬件/系统组合。
- App 使用 ad-hoc 签名，未公证。macOS 可能需要标准 GUI 的“仍要打开”，首次录音需要麦克风权限。
- 语言菜单不代表每种语言/模型组合都完成实音频测试。历史 1.0.0 的 M4 Max/M5 验收不自动扩张为本包的兼容矩阵。
- 重叠音频切片可能出现少量时间戳回退；保守去重可能保留重复短句或标点。
- Clean 文件操作保持 single-writer、无外部文件锁的边界。
