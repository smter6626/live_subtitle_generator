# product_polish_runtime.md

最后更新：2026-08-20  
文档角色：`main` 分支 Product / UX polish 动态执行状态

本文件承接 `docs/deployment_runtime.md` 在 Step 8 / Step 9 实机验收中记录的非阻塞使用体验问题。Deployment Step 9 与 Release 0.2.0 已经 PASS，不重新打开；本文件从 **Step 10** 开始管理后续小范围 Product / UX polish。

长期不可破坏边界继续以 `docs/deployment_static.md` 为准。本文件只管理当前 Product / UX polish 的 ACTIVE step、验收、回归和完成记录。

---

## 0. 使用规则

1. 当前分支固定为 `main`。
2. Step 10 继续使用当前 main，不为每个小 Step 新建 branch。
3. 一个明确子 Step 一个 commit；自检通过后 push 当前 `main`。
4. Codex 不自行创建 branch，不 merge / rebase / reset / stash / force push。
5. 如果当前 branch 不是 `main`、worktree 有未说明修改、或 `origin/main` 在执行期间意外前进，立即停止并汇报。
6. Codex 默认只读取本文件，不主动修改本文件；每个子 Step 完成后由人工 / ChatGPT 审核实现，再推进 ACTIVE step。
7. Step 10 只处理本文件明确列出的 Product / UX polish，不借机重构稳定 ASR 主链路。

通常流程：

```text
Codex 执行当前 Step 10x
-> tests / build / self-check
-> 一个 commit
-> push main
-> 人工 / ChatGPT 审核 GitHub 实际实现
-> 更新 product_polish_runtime.md
-> 激活下一子 Step
```

---

## 1. 当前 checkpoint

```text
branch: main
Step 10 起点 main: 7930cc3255e8ae1f0dbc3755e4a78e09f4e7b00f
起点内容: docs: complete deployment step 9
Release baseline: 0.2.0
Deployment Step 9: PASS
Product / UX Step 10: ACTIVE
唯一 ACTIVE: Step 10A - Current-model panel readability
```

当前 Step 10 状态：

```text
10A Current-model panel readability                 ACTIVE
10B Model selection transient confirmation          PENDING
10C Model download visible progress / busy feedback PENDING
10D Configurable output root                        PENDING
10E Step 10 packaged regression / acceptance        PENDING
```

Step 10 总目标：

> **在不触碰稳定 ASR 算法与 evidence semantics 的前提下，把 Step 8 / 9 实机使用中已经确认的几个非阻塞 UX 问题修到可长期使用的状态。**

---

## 2. Step 10 共同硬约束

### 2.1 稳定 ASR 主链路继续冻结

默认禁止修改：

```text
audio capture
ring buffer
10s chunk / 3s overlap 调度
48k -> 16k resample
WhisperCppBackend 推理语义
simple_dedup()
fuzzy_boundary_dedup()
TranscriptStore raw / clean 写入语义
Stop / microphone release 主逻辑
```

如果某个 UX Step 被证明必须修改这些区域才能完成，Codex 先停止并汇报，不自行扩大 scope。

### 2.2 Evidence layer 不变

每个 session 仍必须产生：

```text
raw.txt
clean.txt
session.log
config.json
```

Step 10 不得修改、覆盖、追加其他语义到这些文件来实现 UX；尤其不能改变 raw/clean 的内容合同。

### 2.3 Model integrity contract 不变

Step 10C 可以改善下载过程的可见性，但不得弱化或绕过：

```text
hidden staging
exact size validation
SHA-256 validation
atomic publish
integrity receipt
only verified model becomes available/selectable
```

网络下载与 SHA-256 仍必须在后台 worker，不进入 Qt 主线程。

### 2.4 UI / settings 修改原则

允许小范围修改：

```text
ui_app.py
model_manager.py
settings.py
resource_paths.py
transcription_controller.py
与上述 UX 行为直接相关的 tests/docs
```

但必须优先最小改动。不要因为 Step 10 做 UI framework 重构、controller 重构或 Model Manager 重写。

### 2.5 Packaging / Release 回归

Step 10 每个子 Step 至少执行相关 unit / contract tests；10E 必须重新执行正式 packaged App build + packaged Runtime verifier，并人工做最小 GUI smoke。

Step 10 默认不创建新 GitHub Release/tag。是否发布 0.2.1 / 0.3.0 等版本由 Step 10 完成后用户另行决定。

---

## 3. Step 10A - Current-model panel readability

状态：**ACTIVE**。

### 3.1 已知问题

当前 `ModelInfo.display_label` 把：

```text
name | size | full/relative path | status
```

组合成一个字符串。主窗口当前模型区域直接显示该 label；当模型位于较长的用户绝对路径时，路径会主导视觉区域，模型名/大小/状态的可读性下降。

Model Manager 的模型表格本身已有单独 Path 列，不需要为了本 Step 删除路径信息。

### 3.2 目标

让主窗口和 Model Manager 的“当前模型”摘要优先显示：

```text
模型名
大小
available / integrity 状态
```

完整路径仍然可访问，但不应持续占满主摘要区域。

Codex 先阅读 `ui_app.py` / `model_manager.py` 当前实现，再选择最小、符合 Qt 行为的呈现方式。允许方案包括：

```text
concise summary + full-path tooltip
middle-elided path + tooltip
可选择/复制的 path detail
```

不要为了实现 elide 引入复杂 custom widget，除非现有 Qt 控件无法满足最低验收。

### 3.3 验收标准

```text
[ ] 默认 1200x800 主窗口中 current model 首先可读到模型名
[ ] size / status 仍可见或可明确获取
[ ] 长 absolute path 不再压倒主摘要
[ ] 完整 path 仍可通过 tooltip 或等价非破坏方式查看
[ ] Model Manager table 的 Path 信息没有丢失
[ ] model selection / availability / integrity semantics 完全不变
[ ] Start / Stop 可用性逻辑不变
```

### 3.4 最低测试

先审计现有 tests；新增/调整最小 UI contract test，至少覆盖 long-path model 的显示语义。

建议实际执行：

```text
.venv/bin/python -m py_compile ui_app.py model_manager.py
.venv/bin/python -m unittest discover -s testCodes -p 'test_*model*ui*.py' -v
.venv/bin/python -m unittest discover -s testCodes -p 'test_*model*.py' -v
git diff --check
git status --short
```

若现有测试文件名不同，以 repo 实际 test suite 为准，不要为了匹配命令复制测试。

完成后一个 commit，建议语义：

```text
fix: improve current model readability
```

---

## 4. Step 10B - Model selection transient confirmation

状态：PENDING。

### 4.1 已知问题

当前模型选择成功会更新状态并写 log，但普通用户缺少一个短时、直观的成功反馈。

### 4.2 目标

成功选择模型后显示约 2 秒的 **non-modal transient confirmation**，例如：

```text
已成功选择模型：large-v3
Model selected: large-v3
```

要求：

```text
不弹 modal QMessageBox
不阻塞 UI 主线程
自动消失
只在实际 successful selection 后触发
refresh / scan 不应伪装成“用户选择成功”
中英文沿用现有 TEXT / translation 机制
```

具体用 status bar、临时 QLabel、overlay 或现有 UI 中最小可靠方式，由 Codex 根据实际 Qt 结构选择。

### 4.3 验收

```text
[ ] 成功选择后出现明确确认
[ ] 约 2 秒自动消失
[ ] 不阻塞 Model Manager / MainWindow
[ ] failed/unavailable selection 不显示 success
[ ] selected model persistence 不变
[ ] Start 使用的仍是被选中的同一模型
```

建议 commit：

```text
fix: add model selection confirmation
```

---

## 5. Step 10C - Model download visible progress / busy feedback

状态：PENDING。

### 5.1 已知问题

大模型例如 `large-v3` 下载时间较长。当前下载已经在后台线程运行，按钮会被 disable，日志也有输出，但主界面缺少持续可见的 progress / spinner / busy feedback，用户容易误判为卡死。

### 5.2 目标

下载期间必须有持续可见的活动反馈。

最低可接受实现：

```text
indeterminate progress bar / busy indicator
+ 当前正在下载的 model name
+ 明确 downloading 状态
```

如果现有 downloader 输出中存在**稳定、可测试、不会耦合 upstream 文本格式**的 byte progress，可以实现 determinate bytes/percent；否则不要为了百分比进度去解析脆弱的 shell/curl 输出。

本 Step 的优先级是：

```text
用户知道下载仍在进行
> 精确百分比
```

### 5.3 硬约束

不得改坏 Step 7 integrity transaction。尤其：

```text
不得把网络或 hash 移回 UI thread
不得在验证完成前显示 model available
不得绕过 staging / SHA / receipt
失败/重试仍 fail closed
```

### 5.4 验收

```text
[ ] 下载开始后立即出现 visible busy/progress feedback
[ ] feedback 显示当前 model
[ ] 下载成功后结束 busy 状态并正常 select verified model
[ ] 下载失败后结束 busy 状态并显示错误
[ ] dialog 关闭保护仍正确
[ ] UI 不冻结
[ ] size/SHA/atomic publish/receipt tests 全部继续 PASS
```

建议 commit：

```text
fix: show model download progress state
```

---

## 6. Step 10D - Configurable output root

状态：PENDING。

这是 Step 10 中风险最高的一项，必须在 10A-C 通过后单独做。

### 6.1 已知现状

Frozen App 默认输出为：

```text
~/Documents/ClassroomTranscriber/outputs/<timestamp>/
```

`TranscriptStore` 当前接收的是 `.../outputs` 目录，并在其下创建 `<timestamp>` session directory。

### 6.2 目标语义

用户配置的是 **ClassroomTranscriber output base/root**，默认仍为：

```text
~/Documents/ClassroomTranscriber
```

选择其他 root 后，新 session 必须继续形成：

```text
<chosen-root>/outputs/<timestamp>/raw.txt
<chosen-root>/outputs/<timestamp>/clean.txt
<chosen-root>/outputs/<timestamp>/session.log
<chosen-root>/outputs/<timestamp>/config.json
```

禁止改成：

```text
<chosen-root>/<timestamp>/...
```

因为 `outputs/<timestamp>/...` 子结构是当前产品合同的一部分。

### 6.3 Persistence

新的 root 必须持久化到 app settings，只影响**之后新建的 session**；不得移动、重命名或修改历史 session。

如果用户配置目录失效 / 不可写：

```text
Start 前 fail clearly
不得半途 fallback 到未知路径
不得创建半个 session 后再切目录
```

可以保留默认值向后兼容：旧 settings 没有该字段时继续使用 `~/Documents/ClassroomTranscriber`。

### 6.4 实现边界

允许在 settings / controller 参数传递层新增 output root，但尽量保持 `TranscriptStore(output_root)` 的既有语义：最终传入 TranscriptStore 的仍应是 `<base>/outputs`。

不要修改 TranscriptStore 的 raw/clean/log/config filename 或 append semantics。

### 6.5 验收

```text
[ ] 默认路径行为完全不变
[ ] UI 可选择新的 output base/root
[ ] 设置重启后持久化
[ ] 新 session 写到 <chosen-root>/outputs/<timestamp>/
[ ] 四个 evidence 文件存在且语义不变
[ ] Stop -> Start 后继续在 chosen root 下生成新的 timestamp session
[ ] 历史 session 不被移动/修改
[ ] invalid/unwritable root 明确 fail
[ ] config/settings 不泄露任何 secret
```

建议 commit：

```text
feat: add configurable output root
```

---

## 7. Step 10E - Packaged regression / acceptance

状态：PENDING。

10A-D 全部经实现审核后执行一次 Step 10 收口，不再顺手增加功能。

必须覆盖：

```text
formal one-entry build
packaged Runtime verifier
Model Manager basic scan/select
fresh small model download（建议 base.en）
selection transient confirmation
long-path current-model readability
custom output root
Start -> real transcription -> Stop
Stop -> second Start
raw/clean/session.log/config.json evidence
repo worktree clean
```

优先在 M5 Developer / Reference Machine 完成开发回归；如果 Step 10 改动只涉及 UI/settings 且 packaged regression PASS，不默认要求重新跑 35 分钟 M4 classroom test。若实际实现触碰 Runtime/ASR 边界，则升级验收并停止由人工决定。

Step 10E PASS 后再由用户决定是否：

```text
发布新的 GitHub Release
恢复 llm-sidecar-phase1
继续其他 Product / UX backlog
```

---

## 8. 明确不进入 Step 10 的项目

以下仍不是本轮目标：

```text
M4 Max 再重复 fresh Model Manager download 的纯验收动作
M4 长课堂偶发一次 inference latency spike 的优化
Developer ID signing
notarization
DMG
GitHub Actions
minimum macOS
M1/M2/M3 实机验证
LLM sidecar
session browser
persistent whisper backend
ASR chunk/backend 重构
```

其中 M4 fresh model repeat 和偶发 latency spike 继续作为 non-blocking observation；除非后续产生可重复失败证据，否则不升级成 Step 10 bugfix。

---

## 9. 当前下一步

只执行 **Step 10A**。

Codex 开始前必须：

```text
cd /Users/smter-mac/Documents/personalAPPS/whisper
git fetch origin
git branch --show-current
git status --short
git rev-parse HEAD
git rev-parse origin/main
```

预期在拉取本 runtime governance commit 后：

```text
branch = main
worktree = clean
HEAD == origin/main
```

若只是 clean main 落后：允许 `git pull --ff-only origin main`。

Step 10A 只做 current-model readability，不提前做 toast、download progress 或 output-root。

---

## 10. 上下文恢复入口

Product / UX Step 10：

```text
1. docs/deployment_static.md
2. docs/deployment_runtime.md
3. docs/product_polish_runtime.md
4. ui_app.py
5. model_manager.py
6. settings.py
7. resource_paths.py
8. transcription_controller.py（仅 output-root Step 需要）
9. transcript_store.py（合同参考，默认避免修改）
10. 相关 testCodes/
```

Release / Deployment 历史继续由 `docs/deployment_runtime.md` 保存；不要把 Step 10 的 ACTIVE 状态写回 LLM runtime。