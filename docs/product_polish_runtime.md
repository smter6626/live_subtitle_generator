# product_polish_runtime.md

最后更新：2026-08-20  
文档角色：`main` 分支 Product / UX polish 动态执行状态（runtime state）

本文件承接 `docs/deployment_runtime.md` 在 Step 8 / Step 9 实机验收中记录的非阻塞使用体验问题。Deployment Step 9 与 Release 0.2.0 已经 PASS，不重新打开。

Product / UX polish 的长期目标与硬边界见：`docs/product_polish_static.md`。Deployment 长期合同继续见 `docs/deployment_static.md`。本文件只记录当前 checkpoint、唯一 ACTIVE Step、已经确认的代码事实、各子 Step 的完整执行计划、验收与完成记录。

---

## 0. 使用规则

1. 当前分支固定为 `main`。
2. Product / UX polish 从 **Step 1** 开始编号，不继承 Deployment 的 Step 10 编号。
3. 当前工作线继续使用 `main`，不为每个小 Step 新建 branch。
4. 一个明确子 Step 一个 commit；自检通过后 push 当前 `main`。
5. Codex 不自行创建 branch，不 merge / rebase / reset / stash / force push。
6. 如果当前 branch 不是 `main`、worktree 有未说明修改、或 `origin/main` 在执行期间意外前进，立即停止并汇报。
7. Codex 默认读取本文件与 `docs/product_polish_static.md`，但不主动修改 runtime；每个子 Step 完成后由人工 / ChatGPT 审核实现，再推进 ACTIVE step。
8. 已经能从当前 repo 明确确认的实现事实直接记录在本文件，不在“下一步”中压缩成模糊摘要，也不要求后续 Codex 重新猜测这些事实。
9. Product / UX polish 只处理 static/runtime 明确列出的体验问题，不借机重构稳定 ASR 主链路。
10. Codex prompt 的实现分工、机器等价原则以 `docs/product_polish_static.md` 5.1 为准：prompt 负责目标/边界/验收，不替 Codex 预先规定非合同性的代码实现细节，也不在普通 Product Step 中强调当前开发机器。

通常流程：

```text
Codex 执行当前 Step 1x
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
Product implementation baseline: 7930cc3255e8ae1f0dbc3755e4a78e09f4e7b00f
baseline 内容: docs: complete deployment step 9
Release baseline: 0.2.0
Deployment Step 9: PASS
Product / UX Step 1: ACTIVE
唯一 ACTIVE: Step 1A - Current-model panel readability
```

Product / UX governance 已建立：

```text
db96a25db5be14a28a0fb5e650e209165dfa0d38  docs: activate product polish step 10（历史初始化，编号已在本文件修正）
c10cfa64ef952ed46374d5cb02d2c5a72cc5b2d2  docs: define product polish contract
86fe495fe4d8a6311a32fa5ceb932523bc8d863a  docs: renumber product polish to step 1
119247c62ec18010f83cd98fdffa2f14f9651ea9  docs: refine product polish contract
```

当前 Step 1 状态：

```text
1A Current-model panel readability                 ACTIVE
1B Model selection transient confirmation          PENDING
1C Model download visible progress / busy feedback PENDING
1D Configurable output root                        PENDING
1E Packaged regression / acceptance                PENDING
```

Step 1 的四个产品目标已经冻结到 `docs/product_polish_static.md`：

```text
Current-model readability
Model-selection transient confirmation
Model-download visible busy/progress feedback
Configurable output root while preserving outputs/<timestamp>/evidence structure
```

1E 是整轮 packaged regression / acceptance，不是额外产品功能。

Deployment 遗留的 M4 Max fresh Model Manager repeat 已在 2026-08-20 后续实测中关闭：

```text
Release App
-> Model Manager 自选模型目录
-> fresh download base.en
-> 使用 base.en 实际转录
-> PASS
```

该事项不再是 Product / UX open observation，也不影响 Step 1A-C 对 Model Manager UX 的独立改进目标。

---

## 2. 当前 repo 已确认的实现事实

这些内容已经从当前 `main` 代码确认，后续 Step 应直接基于这些事实设计最小修改；除非实际代码在执行前发生变化，不需要把它们重新降级成“待调查”。

### 2.1 Current-model display

`model_manager.py` 当前 `ModelInfo.display_label` 为：

```text
name | size | display_path | status
```

`ui_app.py` 的 MainWindow `_update_model_labels()` 在主窗口 current-model 区域直接使用：

```text
self.model_current_label.setText(self.selected_model.display_label)
self.model_current_label.setToolTip(str(self.selected_model.path))
```

因此长 absolute path 会持续进入主摘要文本；完整路径其实已经同时存在于 tooltip。

Model Manager dialog 当前模型摘要也使用 `display_label`。与此同时 Model Manager table 已独立分成：

```text
Name | Size | Path | Status
```

Path 列本身不会因为主摘要精简而丢失。

### 2.2 Model selection

Model Manager `_select_model()` 当前会：

```text
更新 selected_model
写 app settings
更新 current label
emit model_selected
写 INFO log
```

MainWindow `_set_selected_model()` 当前会：

```text
更新 selected_model
持久化 selected_model_path / selected_model_name
刷新 model combo / labels / status
```

当前没有约 2 秒 non-modal success confirmation；已有的是状态刷新和 log，不等价于短时用户反馈。

### 2.3 Model download

Model Manager 当前已经有：

```text
self.downloading
self.downloading_model_name
background threading.Thread(..., daemon=True)
_set_download_controls(False/True)
log_message
_handle_download_finished()
reject() 时阻止下载中直接关闭 dialog
```

`download_and_publish_model()` 继续走 Step 7 integrity transaction。网络下载和最终验证工作已经不在 Qt 主线程。

当前 UI 没有持续可见的 QProgressBar / spinner / busy widget；下载期间主要依靠按钮 disabled 和 log 判断活动状态。因此本 Step 的缺口是“可见 busy/progress feedback”，不是重新设计 downloader。

### 2.4 Output path

`resource_paths.py` 当前 Frozen App 默认：

```text
user_documents_dir() = ~/Documents/ClassroomTranscriber
writable_outputs_dir() = ~/Documents/ClassroomTranscriber/outputs
```

`settings.py` 当前：

```text
OUTPUTS_DIR = writable_outputs_dir()
TranscriptionSettings.output_root 默认 = OUTPUTS_DIR
```

`AppSettings` 目前保存模型相关设置和 beam，不包含 configurable output base/root。

`transcription_controller.py` 当前在 start 时：

```text
self.settings = default_settings(...)
self.store = TranscriptStore(self.settings.output_root)
```

`TranscriptStore` 当前把传入的 `output_root` 当作实际 `.../outputs` 目录，并在其下创建 `<timestamp>` session directory。

因此 1D 的最小正确方向已经明确：用户配置的是 base/root；settings/controller 计算最终 `<base>/outputs` 后继续传给现有 TranscriptStore，而不是改写 TranscriptStore 的 evidence filename/append semantics。

---

## 3. Step 1 共同执行约束

长期合同以 `docs/product_polish_static.md` 为准，当前执行中尤其保护：

```text
audio capture
ring buffer
10s chunk / 3s overlap scheduling
48k -> 16k resample
WhisperCppBackend inference semantics
simple_dedup()
fuzzy_boundary_dedup()
TranscriptStore raw / clean append semantics
Stop / microphone release 主逻辑
```

Evidence layer 继续固定：

```text
raw.txt
clean.txt
session.log
config.json
```

1C 不得弱化：

```text
hidden staging
exact size validation
SHA-256 validation
atomic publish
integrity receipt
only verified model becomes available/selectable
```

每个子 Step 至少执行相关 unit / contract tests；1E 必须正式 packaged build + packaged Runtime verifier + GUI smoke。

Step 1 默认不创建新 GitHub Release/tag。是否发布后续版本由 Step 1 完成后用户另行决定。

---

## 4. Step 1A - Current-model panel readability

状态：**ACTIVE**。

### 4.1 已知问题与代码锚点

问题不是 path 不可访问，而是 path 已经被塞进摘要文本：

```text
ModelInfo.display_label
-> MainWindow.model_current_label
-> ModelManagerDialog.current_label
```

主窗口已经有 full-path tooltip；Model Manager table 也已经有独立 Path 列。因此不需要为了本 Step 新增复杂 path storage 或 custom model object。

### 4.2 目标

主窗口和 Model Manager 的“当前模型”摘要优先显示：

```text
模型名
大小
available / integrity 状态
```

完整路径仍可通过 tooltip 或等价方式访问，但不持续占满主摘要。

优先采用最小实现，例如新增一个专门的 concise summary property/helper，而保留现有 `display_label` 给 combo/table/log 等仍需要完整信息的场景；最终方案由 Codex 根据调用点审计决定，不要求机械采用该名字。

不要为了 ellipsis 引入复杂 custom widget，除非现有 QLabel/tooltip 方案不能满足验收。

### 4.3 允许修改范围

预计主要：

```text
model_manager.py
ui_app.py
相关 UI/model tests
```

不应需要修改 controller、engine、TranscriptStore、model integrity 或 downloader。

### 4.4 验收标准

```text
[ ] 默认 1200x800 主窗口 current model 首先可读到模型名
[ ] size / status 可见或明确可获取
[ ] 长 absolute path 不再压倒主摘要
[ ] 完整 path 仍可通过 tooltip 或等价非破坏方式查看
[ ] Model Manager current summary 同样改善
[ ] Model Manager table 的 Path 信息没有丢失
[ ] combo / log 如仍需要完整 display_label，不被无意破坏
[ ] model selection / availability / integrity semantics 完全不变
[ ] Start / Stop 可用性逻辑不变
```

### 4.5 最低测试

Codex 先审计现有相关 tests，再新增/调整最小 UI contract test，至少覆盖 long-path model 的摘要和 full-path 可访问性。

实际命令至少包括：

```text
.venv/bin/python -m py_compile ui_app.py model_manager.py
.venv/bin/python -m unittest discover -s testCodes -p 'test_*model*ui*.py' -v
.venv/bin/python -m unittest discover -s testCodes -p 'test_*model*.py' -v
git diff --check
git status --short
```

若实际 test 文件命名不同，以 repo 已有 suite 为准；不要为了匹配 glob 复制测试。

完成后一个 commit，建议：

```text
fix: improve current model readability
```

---

## 5. Step 1B - Model selection transient confirmation

状态：PENDING。

### 5.1 已知问题与代码锚点

当前 successful selection 已经有 persistence / label refresh / INFO log，但没有 transient user-facing confirmation。

主要成功入口目前包括：

```text
ModelManagerDialog._select_model()
MainWindow._set_selected_model()
```

需要避免 refresh / initial scan 触发假 success；因此应该围绕真实 user selection event 设计，而不是任何 `_update_model_labels()` 都触发。

### 5.2 目标

实际成功选择模型后显示约 2 秒的 **non-modal transient confirmation**，例如：

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
refresh / scan / startup restore 不显示 success
failed / unavailable selection 不显示 success
中英文沿用现有 TEXT / translation 机制
```

可以使用 status bar、临时 QLabel 或现有 UI 最小可靠机制；不为 toast 引入新的 UI framework。

### 5.3 验收

```text
[ ] 成功选择后出现明确确认
[ ] 约 2 秒自动消失
[ ] 不阻塞 Model Manager / MainWindow
[ ] failed/unavailable selection 不显示 success
[ ] startup/refresh 不产生伪 success
[ ] selected model persistence 不变
[ ] Start 使用的仍是同一 selected model
```

最低测试应覆盖 success / unavailable / refresh-no-toast / auto-clear timer 的 contract；具体 Qt test 方式以现有 test 架构为准。

建议 commit：

```text
fix: add model selection confirmation
```

---

## 6. Step 1C - Model download visible progress / busy feedback

状态：PENDING。

### 6.1 已知问题与代码锚点

当前下载已经是后台线程，且有 downloading flag、model name、disabled controls、log 和 finished signal；真正缺失的是 dialog 中持续可见的 activity indicator。

因此本 Step 不需要重写 download transaction，也不需要把 downloader 输出改造成新的协议。

### 6.2 目标

下载期间必须持续显示可见活动反馈。

最低可接受实现：

```text
indeterminate progress bar / busy indicator
+ 当前正在下载的 model name
+ 明确 downloading / verifying / finished/failed 中至少足以避免“卡死”误判的状态
```

如果现有 downloader 输出存在稳定、可测试、且不依赖 upstream 文本格式的 bytes progress，可以做 determinate progress；否则保持 indeterminate。

优先级：

```text
用户知道下载仍在进行
> 精确百分比
```

### 6.3 硬约束

```text
网络和 SHA-256 不进入 Qt 主线程
验证完成前不得显示 available
不绕过 staging / size / SHA / atomic publish / receipt
失败和重试继续 fail closed
reject() 的下载中关闭保护继续成立
```

### 6.4 验收

```text
[ ] 下载开始后立即出现 visible busy/progress feedback
[ ] feedback 显示当前 model
[ ] 长下载期间 feedback 持续存在
[ ] 下载成功后结束 busy 状态并正常 select verified model
[ ] 下载失败后结束 busy 状态并显示错误
[ ] dialog 关闭保护正确
[ ] UI 不冻结
[ ] size/SHA/atomic publish/receipt tests 全部继续 PASS
```

最低测试必须包含 success/failure 两条 UI state transition，并继续跑 model integrity tests。

建议 commit：

```text
fix: show model download progress state
```

---

## 7. Step 1D - Configurable output root

状态：PENDING。

这是 Step 1 中风险最高的一项，必须在 1A-C 通过后单独做。

### 7.1 已知现状

Frozen App 默认链路已经确认：

```text
resource_paths.user_documents_dir()
-> ~/Documents/ClassroomTranscriber
resource_paths.writable_outputs_dir()
-> ~/Documents/ClassroomTranscriber/outputs
settings.OUTPUTS_DIR
-> TranscriptionSettings.output_root
controller.start()
-> TranscriptStore(settings.output_root)
-> <output_root>/<timestamp>/...
```

当前 AppSettings 没有用户可配置 output base/root 字段。

### 7.2 目标语义

用户配置的是 ClassroomTranscriber **output base/root**，默认仍为：

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

禁止变成：

```text
<chosen-root>/<timestamp>/...
```

### 7.3 Persistence / validation

新的 base/root 必须保存到 app settings，只影响之后新建 session；不得移动、重命名或修改历史 session。

旧 settings 没有该字段时继续默认 `~/Documents/ClassroomTranscriber`。

invalid/unwritable root：

```text
Start 前明确 fail
不得静默 fallback 到另一目录
不得先创建半个 session 再切换
```

### 7.4 实现边界

优先在：

```text
AppSettings/settings persistence
UI folder chooser
TranscriptionSettings/default_settings/controller parameter passing
```

完成 base -> `<base>/outputs` 的转换。

尽量保持：

```text
TranscriptStore(output_root)
```

的现有语义不变，也不修改 raw/clean/session.log/config.json filename 与 append 行为。

### 7.5 验收

```text
[ ] 默认路径行为完全不变
[ ] UI 可选择新的 output base/root
[ ] 设置重启后持久化
[ ] 新 session 写到 <chosen-root>/outputs/<timestamp>/
[ ] 四个 evidence 文件存在且语义不变
[ ] Stop -> Start 后在 chosen root 下生成新的 timestamp session
[ ] 历史 session 不移动/不修改
[ ] invalid/unwritable root 在 Start 前明确失败
[ ] 不出现 silent fallback
```

测试必须覆盖 default/backward compatibility、custom root、persistence、unwritable failure、controller->store path contract。

建议 commit：

```text
feat: add configurable output root
```

---

## 8. Step 1E - Packaged regression / acceptance

状态：PENDING。

1A-D 全部经 GitHub 实际实现审核通过后执行一次整轮收口，不再顺手增加功能。

必须覆盖：

```text
formal one-entry build
packaged Runtime verifier
long-path current-model readability
Model Manager basic scan/select
selection transient confirmation
fresh small model download（建议 base.en）
visible download busy/progress feedback
model integrity available/selectable
custom output root + persistence
Start -> real transcription -> Stop
Stop -> second Start
new timestamp session under chosen root
raw.txt / clean.txt / session.log / config.json evidence
repo worktree clean
```

Packaged regression 可在任一当前已验证的 Apple Silicon 开发机完成；普通 Product / UX 回归不按 M4 Max / M5 分配固定角色。

如果 1A-D 实际只触及 UI/settings/controller 参数层且所有 packaging / ASR regression PASS，不默认要求重复此前约 35 分钟课堂测试；若实现触碰 Runtime/ASR 冻结边界，则在 1E 前停止并升级验收。

1E PASS 后再由用户决定：

```text
是否发布新 GitHub Release
是否恢复 llm-sidecar-phase1
是否开启新的 Product / UX Step
```

---

## 9. 明确不进入 Step 1 的项目

```text
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

此前 Deployment 遗留的 M4 fresh Model Manager repeat 已完成，不再列为 Product / UX non-blocking observation。剩余的偶发 latency spike 继续作为 non-blocking observation；除非产生可重复失败证据，否则不升级成当前 Product / UX bugfix。

---

## 10. 当前 ACTIVE / 下一步执行

当前只执行 **Step 1A - Current-model panel readability**。

开始前必读：

```text
docs/product_polish_static.md
docs/product_polish_runtime.md
docs/deployment_static.md
README.md
```

实现时直接使用第 2 节已经确认的代码事实，不需要把“display_label 是否包含 path”“tooltip 是否已存在”“Model Manager 是否已有独立 Path 列”重新作为未知问题。

Codex 开始前在**当前已同步的项目 clone 根目录**执行：

```text
pwd
git fetch origin
git branch --show-current
git status --short
git rev-parse HEAD
git rev-parse origin/main
```

要求：

```text
branch = main
worktree = clean
HEAD == origin/main
```

如果只是 clean main 落后，允许：

```text
git pull --ff-only origin main
```

Step 1A 的实施范围、验收和最低测试完整定义在第 4 节；不要为了“下一步提示”另行压缩成更弱的目标。

Step 1A 完成后：

```text
相关 tests PASS
必要 UI contract test 已补
一个 commit
push main
最终 worktree clean
Codex 不修改 product_polish_runtime.md
```

然后由人工 / ChatGPT 审核 GitHub 实际 diff。审核 PASS 后再把 1A 标记为 PASS，并激活本文件第 5 节已经完整定义的 1B；1B/1C/1D 的已知实现事实和验收标准保留在本文件，不因尚未 ACTIVE 而删减。

---

## 11. 上下文恢复入口

Product / UX Step 1：

```text
1. docs/product_polish_static.md
2. docs/product_polish_runtime.md
3. docs/deployment_static.md
4. docs/deployment_runtime.md
5. README.md
6. ui_app.py
7. model_manager.py
8. settings.py
9. resource_paths.py
10. transcription_controller.py（1D 重点）
11. transcript_store.py（合同参考，默认避免修改）
12. 相关 testCodes/
```

Release / Deployment 历史继续由 `docs/deployment_runtime.md` 保存；不要把 Product / UX Step 1 的 ACTIVE 状态写回 LLM runtime。
