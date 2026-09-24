# Change Records

本目录保存已经落到本仓库代码上的重要变更记录。目标是让维护者只读取目标仓库，也能理解变更原因、稳定行为、验证范围、已知限制和后续方向。

这些文件不是 Agent 运行日志，也不是第二份 orchestration Runtime：

- 产品行为和当前代码以本仓库 source、tests、manifests 和对应 commit 为准。
- 完整 1PCloop Static、Runtime、checkpoint、prompt、process receipt 和 raw evidence 继续由独立的 `smter6626/framework-loop` 仓库保存。
- 本目录仅保留跨仓库审计所需的 commit、run ID、hash 和紧凑结论，不复制本机绝对路径或完整 Agent payload。

## Records

| Record | 状态 | 说明 |
| --- | --- | --- |
| [Session clipboard UI v1](session_clipboard_ui_v1.md) | 功能 ACCEPT；功能分支尚未 merge/release | Clean 路径复制、新 Session 清屏、增量复制、双语 label、session ownership 和测试结论 |
| [Window layout v1](window_layout_v1.md) | 等待独立审查和 macOS 实机 Human Gate | 主窗口可用屏幕高度约束、左侧控制区滚动和右侧滚动 ownership |

Streaming backend 调查与治理归档已进入目标仓库 `main` 的 [`docs/streaming_backend_upgrade/`](https://github.com/smter6626/live_subtitle_generator/tree/main/docs/streaming_backend_upgrade)，其内容不表示 backend 已完成实现。当前功能分支基于 `multiLanguage_v1`，在完成后续集成前不会包含该独立 `main` 文档提交。
