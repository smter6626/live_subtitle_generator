# product_polish_runtime.md

最后更新：2026-08-21  
文档角色：`main` 分支 Product / UX polish 动态执行状态（runtime state）

本文件承接 `docs/deployment_runtime.md` 在 Step 8 / Step 9 实机验收中记录的非阻塞使用体验问题。Deployment Step 9 与 Release 0.2.0 已经 PASS，不重新打开。

Product / UX polish 的长期目标与硬边界见：`docs/product_polish_static.md`。Deployment 长期合同继续见 `docs/deployment_static.md`。当前代码结构与影响面辅助见 `docs/repo_map.md`。本文件只记录当前 checkpoint、唯一 ACTIVE Step、已经确认的代码事实、各子 Step 的完整执行计划、验收与完成记录。

---

## 0. 使用规则

1. 当前分支固定为 `main`。
2. Product / UX polish 从 **Step 1** 开始编号，不继承 Deployment 的 Step 10 编号。
3. 当前工作线继续使用 `main`，不为每个小 Step 新建 branch。
4. 一个明确子 Step 一个 commit；自检通过后 push 当前 `main`。
5. Codex 不自行创建 branch，不 merge / rebase / reset / stash / force push。
6. 如果当前 branch 不是 `main`、worktree 有未说明修改、或 `origin/main` 在执行期间意外前进，立即停止并汇报。
7. Codex 默认读取本文件、`docs/product_polish_static.md` 与 `docs/repo_map.md`，但不主动修改 runtime；每个子 Step 完成后由人工 / ChatGPT 审核实现，再推进 ACTIVE step。
8. 已经能从当前 repo 明确确认的实现事实直接记录在本文件，不在“下一步”中压缩成模糊摘要，也不要求后续 Codex 重新猜测这些事实。
9. Product / UX polish 只处理 static/runtime 明确列出的体验问题，不借机重构稳定 ASR 主链路。
10. Codex prompt 的实现分工、机器等价原则以 `docs/product_polish_static.md` 5.1 为准：prompt 负责目标/边界/验收，不替 Codex 预先规定非合同性的代码实现细节，也不在普通 Product Step 中强调当前开发机器。
11. 每个实现 Step 审核时都执行 Repo Map impact check；只有 architecture / ownership / interface / data-flow 等事实变化时才更新 `docs/repo_map.md`，不为每个 commit 强制制造 map diff。
12. 2026-08-21 用户明确授权一次 **overnight sequential batch**：在 1C 为唯一 ACTIVE 的前提下，若 1C 自检、commit、push 均通过，可在同一 Codex session 中继续预授权的 1D；1D 同样通过后可继续 1E。三个 Step 仍必须各自独立 scope、tests、commit、push。任一 Step 失败或需要扩大稳定边界时立即停止整个 batch。该例外不授权 1F/1G，也不授权 Codex 修改 runtime/repo_map。
13. 2026-08-21 用户随后明确提供并确认 `icon-live.png` 作为 1F asset，授权实施 1F，并要求本 Step 在 architecture/runtime 状态失真时同步 `docs/repo_map.md` / 本文件；正式构建仍不得保留外部开发机路径。

通常流程：

```text
Codex 执行当前 Step 1x
-> tests / build / self-check
-> 一个 commit
-> push main
-> 人工 / ChatGPT 审核 GitHub 实际实现
-> Repo Map impact check
-> 必要时同步 docs/repo_map.md
-> 更新 product_polish_runtime.md
-> 激活下一子 Step
```

本次 overnight batch 是上述人工 review gate 的一次用户明确授权例外，只适用于 `1C -> 1D -> 1E`，且不改变“一 Step 一 commit”与最终人工审核要求。

---

## 1. 当前 checkpoint

```text
branch: main
Product implementation baseline: 7930cc3255e8ae1f0dbc3755e4a78e09f4e7b00f
baseline 内容: docs: complete deployment step 9
Pre-1F implementation checkpoint: c330744df3de9cdb624aadb4964f0471b125e91b
checkpoint 内容: fix: clarify beam label in chinese ui
Current Product implementation checkpoint: Step 1F App icon integration in this repository snapshot
Release baseline: 0.2.0
Deployment Step 9: PASS
Product / UX Step 1: ACTIVE
唯一 ACTIVE: Step 1G - Packaged regression / acceptance
```

Product / UX governance / architecture map 已建立：

```text
db96a25db5be14a28a0fb5e650e209165dfa0d38  docs: activate product polish step 10（历史初始化，编号已在本文件修正）
c10cfa64ef952ed46374d5cb02d2c5a72cc5b2d2  docs: define product polish contract
86fe495fe4d8a6311a32fa5ceb932523bc8d863a  docs: renumber product polish to step 1
119247c62ec18010f83cd98fdffa2f14f9651ea9  docs: refine product polish contract
878e91e8bc83ef06beb0268139e1ba1095b248a4  docs: extend product polish goals
09425dd3882d35f8c7eb8b8d1aac646e8d40a7d3  docs: schedule additional product polish
15af5c254320b494df774805713d48d2262d1f0a  docs: add repository architecture map
219405494f8c4de719336b9ff6c5e9f94d3445eb  docs: sync repository map after step 1a
aba8f49021e868b75b3bd36bc4d5aa2dfb8ca9c8  docs: sync repository map after step 1b
50a126cb981e66cd87a9e4315896b0500d9bd3a3  fix: show model download progress state
add22acf11ccfa5f92063e0698414e868d987cff  feat: add configurable output root
2c1f7b12f580636d06c0e691fadea47c52b99702  fix: align bilingual ui semantics
c330744df3de9cdb624aadb4964f0471b125e91b  fix: clarify beam label in chinese ui
```

当前 Step 1 状态：

```text
1A Current-model panel readability                 PASS
1B Model selection transient confirmation          PASS
1C Model download visible progress / busy feedback PASS
1D Configurable output root                        PASS
1E 中文 / English UI switch + semantic alignment   PASS
1F Packaged App icon                               PASS
1G Packaged regression / acceptance                ACTIVE
```

Step 1 的六个产品目标已经冻结到 `docs/product_polish_static.md`：

```text
Current-model readability
Model-selection transient confirmation
Model-download visible busy/progress feedback
Configurable output root while preserving outputs/<timestamp>/evidence structure
中文 / English UI switch + semantic alignment
Packaged App icon
```

1G 是整轮 packaged regression / acceptance，不是额外产品功能。

Deployment 遗留的 M4 Max fresh Model Manager repeat 已在 2026-08-20 后续实测中关闭：

```text
Release App
-> Model Manager 自选模型目录
-> fresh download base.en
-> 使用 base.en 实际转录
-> PASS
```

该事项不再是 Product / UX open observation，也不影响 1C 对 Model Manager download UX 的独立改进目标。

---

## 2. 当前 repo 已确认的实现事实

这些内容已经从当前 `main` 代码和已审核实现确认，后续 Step 应直接基于这些事实设计最小修改；除非实际代码在执行前发生变化，不需要把它们重新降级成“待调查”。

### 2.1 Current-model display（Step 1A 后）

`model_manager.py` 当前有两种明确分离的 presentation value：

```text
ModelInfo.current_summary_label
-> name | size | status

ModelInfo.display_label
-> name | size | display_path | status
```

当前消费者已经分离：

```text
MainWindow current-model summary
ModelManagerDialog current-model summary
-> current_summary_label

MainWindow model combo
Model Manager selection / diagnostic logs
-> display_label
```

两个 current-model summary 都保留 full-path tooltip；Model Manager table 继续独立显示 `Name | Size | Path | Status`，因此 path detail 没有因为摘要精简而丢失。

Step 1A 没有改变 model selection、availability/integrity 或 Start gating 语义。

### 2.2 Model selection（Step 1B 后）

当前显式用户选择与自动状态恢复已经在 UI 反馈语义上分离：

```text
MainWindow model combo：
  用户切换到不同且 available model
  -> _on_model_combo_changed()
  -> _set_selected_model()
  -> MainWindow transient confirmation

Model Manager explicit Select：
  用户选中不同且 available row
  -> select_current_row()
  -> _select_model()
  -> dialog transient confirmation
  -> emit model_selected
  -> MainWindow._set_selected_model()
  -> 不产生第二次 MainWindow confirmation
```

两个 surface 各自拥有 parent-owned reusable `QTimer`：

```text
single-shot
2000 ms
timeout -> clear + hide transient QLabel
```

rapid explicit selection 重启同一个 timer，因此旧 timer 不会提前清除新提示。

以下路径明确 **NO CONFIRM**：

```text
verified download completion auto-selection
import 后自动选择
startup persisted-model restore
refresh / scan / reload
unavailable / rejected / failed selection
重复选择当前同一路径模型
```

共享 `_set_selected_model()` / `_select_model()` 负责应用/persist/propagate state，并会清除可能过期的 transient feedback，但不会自行显示 success。Step 1B 不改变 selected model persistence、availability/integrity、Start gating 或 Step 1A presentation contract。

### 2.3 Model download（Step 1C 已完成）

Model Manager 当前已经有：

```text
self.downloading
self.downloading_model_name
background threading.Thread(..., daemon=True)
_set_download_controls(False/True)
log_message
download_finished signal
_handle_download_finished()
reject() 时阻止下载中直接关闭 dialog
```

`download_and_publish_model()` 继续走 Step 7 integrity transaction。网络下载和最终验证工作已经不在 Qt 主线程。

当前 UI 已有 indeterminate `QProgressBar` 和 status label；显式下载期间显示 model name 与 busy 状态，成功/失败完成后统一清除并恢复 controls。实现保留既有 background worker、dialog close protection 与 integrity transaction。

Step 1B 已冻结 download-completion auto-selection 为 `NO CONFIRM`；1C 不应为了 download status UI 改变这一 selection-feedback 语义。

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

`AppSettings` 已向后兼容地保存 `output_base_dir`。MainWindow 提供选择与持久化入口，controller 在 Start 时把 base 映射为 `<base>/outputs`。

`transcription_controller.py` 当前在 start 时：

```text
self.settings = default_settings(...)
self.store = TranscriptStore(self.settings.output_root)
```

`TranscriptStore` 当前把传入的 `output_root` 当作实际 `.../outputs` 目录，并在其下创建 `<timestamp>` session directory。

`validate_runtime_paths()` 在创建 `TranscriptStore` 前验证实际 output root 可创建/可写；失败不 fallback，也不创建半个 session。`TranscriptStore` 的 evidence filename/append semantics 未改。

### 2.5 UI language

当前代码已经有中文 / English 文案基础：

```text
settings.py:
  UI_LANGUAGE_ZH = "zh"
  UI_LANGUAGE_EN = "en"
  DEFAULT_UI_LANGUAGE

ui_app.py:
  TEXT["zh"]
  TEXT["en"]
  current_language()
  tr(...)
```

当前默认 UI language 仍可由进程级配置决定，同时 `AppSettings.ui_language` 提供向后兼容的 persisted choice；MainWindow 有明确中文 / English 入口并实时重绘主窗口与 Model Manager 用户可见文本。

UI language 与音频 `Original Language` / whisper language 继续保持为两套独立概念：前者只改变界面语言，后者决定转录输入语言相关设置。

用户已确认当前版本自己使用没有功能障碍，但对其他用户而言中英文显示与语义组合会显得不统一，因此 1E 是正式 Product polish，而不是 ASR bugfix。

### 2.6 Packaged App icon

当前正式 Release spec 已接入 Manifest-driven icon：

```text
packaging/icons/ClassroomTranscriber.png
-> scripts/build_app_icon.py
-> build/app-icon/ClassroomTranscriber.icns
-> packaging/ClassroomTranscriber.spec BUNDLE(..., icon=str(icon_path), ...)
-> Contents/Resources/ClassroomTranscriber.icns
-> Info.plist CFBundleIconFile=ClassroomTranscriber.icns
```

用户确认的 1254×1254 RGB 源图已原样进入 repo，并由 Manifest 冻结 SHA-256。生成器移除仅与画布边缘连通的浅色 matte，生成 1024×1024 RGBA 完整 iconset / ICNS；派生物只进入 ignored `build/`。formal build 与 Release ZIP 解压后的 App 都通过共享 verifier 检查 ICNS 结构和 `CFBundleIconFile`。

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

1E 不得把 UI language 与 Original Language / whisper language 合并成同一设置。

1F 只在用户确认图标方向 / asset 后进入实施，不提前锁定视觉方案。

每个子 Step 至少执行相关 unit / contract tests；1G 必须正式 packaged build + packaged Runtime verifier + GUI smoke。

Step 1 默认不创建新 GitHub Release/tag。是否发布后续版本由 Step 1 完成后用户另行决定。

---

## 4. Step 1A - Current-model panel readability

状态：**PASS**。

实现 commit：

```text
3a369e55456430a2a5e0b9a55279f1dc1dc2f939
fix: improve current model readability
```

### 4.1 实际实现

新增：

```text
ModelInfo.current_summary_label
= name | size | status
```

主窗口与 Model Manager current summary 使用 `current_summary_label`；原 `display_label` 不删改，继续保留 path 并服务 combo / logs。

两个 current summary 都提供完整模型 path tooltip；Model Manager 独立 Path 列保持不变。

实际 tracked diff：

```text
model_manager.py
ui_app.py
testCodes/test_model_manager_ui_contract.py
```

没有修改 controller、engine、TranscriptStore、model integrity、downloader、settings schema 或 packaging。

### 4.2 GitHub review / 测试 / UI 验收

GitHub diff review、相关 contract/regression tests 与 source UI smoke 均 PASS。核心确认：concise summary/full display 分离、long path 不再压倒 summary、full-path tooltip/Path column 保留、combo/log 不回退、selection/integrity/Start gating 未改变。

Repo Map 因 consumer relationship 改变已在以下 commit 同步：

```text
219405494f8c4de719336b9ff6c5e9f94d3445eb
docs: sync repository map after step 1a
```

---

## 5. Step 1B - Model selection transient confirmation

状态：**PASS**。

实现 commit：

```text
4d2059d273d0ba94373b1969b8236ef462b6acae
fix: add model selection confirmation
```

### 5.1 实际实现

MainWindow model panel 与 Model Manager 各自增加轻量 transient `QLabel` + parent-owned reusable `QTimer`：

```text
single-shot
2000 ms
show -> timer start
timeout -> clear + hide
```

现有双语 `tr("model_selected")` 提供提示文案，提示包含 model name。

confirmation 只从两个显式用户入口触发：

```text
MainWindow combo：不同且 available model -> CONFIRM
Model Manager explicit Select：不同且 available model -> CONFIRM（仅 dialog 一次）
```

自动/恢复路径：

```text
download completion auto-selection -> NO CONFIRM
import auto-selection              -> NO CONFIRM
startup restore                    -> NO CONFIRM
refresh / scan / reload            -> NO CONFIRM
unavailable / failed               -> NO CONFIRM
same-path repeated selection       -> NO CONFIRM
```

共享 setter 不负责显示 success，因此 Model Manager signal propagation 不会产生第二次 MainWindow confirmation。

### 5.2 GitHub review 结果

人工 / ChatGPT 已基于 GitHub commit 实际 diff 审核：

```text
[PASS] confirmation 只绑定显式用户 selection source
[PASS] MainWindow / Model Manager 不 duplicate
[PASS] QTimer parent-owned / single-shot / 2000ms
[PASS] non-modal，无 sleep / worker-thread waiting
[PASS] rapid selection 重启同一 timer
[PASS] download/import/startup/refresh 不显示 selection success
[PASS] unavailable/failed/repeated same-path 不显示 success
[PASS] Step 1A presentation contract 未回退
[PASS] persistence / Start gating / integrity / downloader 未改变
```

### 5.3 测试证据

Codex 报告并通过：

```text
.venv/bin/python -m py_compile ui_app.py model_manager.py
-> PASS

.venv/bin/python -m unittest discover -s testCodes -p 'test_model_manager_ui_contract.py' -v
-> PASS, 8 tests

.venv/bin/python testCodes/test_ui_support.py
-> PASS, 22 checks

.venv/bin/python testCodes/test_model_download_resources.py
-> PASS, 6 checks

.venv/bin/python -m unittest discover -s testCodes -p 'test_*model*.py' -v
-> PASS, 21 tests

.venv/bin/python -m unittest discover -s testCodes -p 'test_*.py' -v
-> PASS, 80 tests

Offscreen Qt event-loop auto-clear smoke
-> PASS; timer active after show, about 2.2s later text cleared and label hidden

git diff --check
-> PASS
```

### 5.4 人工 source UI 验收

用户已在开发源码版完成 targeted UI smoke，并明确确认 PASS：

```text
[PASS] startup 无伪 confirmation
[PASS] main combo 切换提示正常
[PASS] 反复 / rapid switch 提示正常
[PASS] refresh 不产生假提示
[PASS] Model Manager explicit Select 提示正常
[PASS] selection propagation 无 duplicate
[PASS] 当前视觉位置可接受
```

### 5.5 Repo Map impact review

`UPDATE REQUIRED`：Step 1B 新增 event-source -> transient label/timer UI state relationship，并明确 download/import/startup/refresh 等自动路径不产生 confirmation。

Repo Map 已受控同步：

```text
aba8f49021e868b75b3bd36bc4d5aa2dfb8ca9c8
docs: sync repository map after step 1b
```

---

## 6. Step 1C - Model download visible progress / busy feedback

状态：**PASS**（implementation `50a126cb981e66cd87a9e4315896b0500d9bd3a3`）。

### 6.1 实施前问题与代码锚点

实施前下载已经是后台线程，且有 downloading flag、model name、disabled controls、log 和 finished signal；当时真正缺失的是 dialog 中持续可见的 activity indicator。

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
下载中关闭保护继续成立
Step 1B download-completion auto-selection = NO CONFIRM 语义保持
```

### 6.4 验收

```text
[x] 下载开始后立即出现 visible busy/progress feedback
[x] feedback 显示当前 model
[x] 长下载期间 feedback 持续存在
[x] 下载成功后结束 busy 状态并正常 select verified model
[x] 下载失败后结束 busy 状态并显示错误
[x] dialog 关闭保护正确
[x] UI 不冻结
[x] size/SHA/atomic publish/receipt tests 全部继续 PASS
[x] Step 1B selection confirmation 语义不回退
```

最低测试必须包含 success/failure 两条 UI state transition，并继续跑 model integrity tests。

建议 commit：

```text
fix: show model download progress state
```

---

## 7. Step 1D - Configurable output root

状态：**PASS**（implementation `add22acf11ccfa5f92063e0698414e868d987cff`）。

这是前四项中唯一直接改变 session destination 的 Step；它已按 overnight 授权作为独立 commit 完成。

### 7.1 实施前现状

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

实施前 AppSettings 没有用户可配置 output base/root 字段；当前已加入向后兼容的 `output_base_dir`。

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

方向固定为：用户配置 base/root，稳定 session 创建链路最终仍接收 `<base>/outputs` 等价路径。

具体 settings/UI/controller 代码实现由 Codex 根据当前代码上下文选择最小正确方案。

尽量保持：

```text
TranscriptStore(output_root)
```

的现有语义不变，也不修改 raw/clean/session.log/config.json filename 与 append 行为。

### 7.5 验收

```text
[x] 默认路径行为完全不变
[x] UI 可选择新的 output base/root
[x] 设置重启后持久化
[x] 新 session 写到 <chosen-root>/outputs/<timestamp>/
[x] 四个 evidence 文件存在且语义不变
[x] Stop -> Start 后在 chosen root 下生成新的 timestamp session
[x] 历史 session 不移动/不修改
[x] invalid/unwritable root 在 Start 前明确失败
[x] 不出现 silent fallback
```

测试必须覆盖 default/backward compatibility、custom root、persistence、unwritable failure、controller->store path contract。

建议 commit：

```text
feat: add configurable output root
```

---

## 8. Step 1E - 中文 / English UI switch + semantic alignment

状态：**PASS**（implementation `2c1f7b12f580636d06c0e691fadea47c52b99702`，label follow-up `c330744df3de9cdb624aadb4964f0471b125e91b`）。

本 Step 已按 overnight 授权作为独立 commit 完成；后续 label follow-up 只澄清中文 beam 语义。

### 8.1 实施前问题

实施前代码已有中英文 `TEXT` 文案和 UI language 常量，但普通用户缺少明确切换入口，且两套 UI 存在语义未完全对齐的情况；当前已加入 persisted selector 与 live retranslation。

用户本人当前使用没有功能障碍，但其他用户使用时会显得混乱，因此需要在对外产品化前系统清理。

### 8.2 目标

提供明确的中文 / English UI 选择，并对两套界面的主要用户可见语义进行一次完整对齐。

重点是**同一产品语义**，而不是逐字逐句翻译。

必须明确区分：

```text
UI Language
!=
Original Language / whisper input language
```

切换 UI language 不得改变当前 ASR 的 Original Language、whisper language code、模型、beam 或 session evidence semantics。

### 8.3 当前冻结验收

```text
[x] 普通用户可以在 UI 中明确选择 中文 / English
[x] 主窗口主要按钮、状态、Model Manager、session 信息、错误提示在两种 UI 下语义对应
[x] 不存在明显因漏翻译造成的无意中英混杂
[x] 必要技术术语可以保留，但两种 UI 使用方式一致
[x] UI language 与 Original Language 的标签/交互不会让普通用户误以为是同一设置
[x] 切换 UI language 不改变 ASR runtime 配置
[x] Start / Stop / model selection / download / output-root 行为不受破坏
```

实际实现持久化 UI language，并由当前 MainWindow / Model Manager 生命周期即时重绘现有用户可见 widget；没有改变 Original Language 或 ASR runtime 设置。

建议 commit 语义：

```text
fix: align bilingual ui semantics
```

---

## 9. Step 1F - Packaged App icon

状态：**PASS**。

### 9.1 已知现状

正式 PyInstaller Release spec 当前使用 Manifest 生成的 ICNS：

```text
BUNDLE(..., icon=str(icon_path), ...)
```

正式源图为 `packaging/icons/ClassroomTranscriber.png`；Manifest 冻结 source SHA、generator、generated ICNS 和 bundle target。

### 9.2 目标

给正式 packaged `ClassroomTranscriber.app` 加入项目自定义图标，使 Finder / Dock / 后续 Release artifact 不再使用默认 / 无图标表现。

### 9.3 实际设计

用户确认的源图是 1254×1254 RGB、无 alpha。仓库保留原始 approved source；生成器在正式 build 中确定性地移除 edge-connected light matte、生成 1024 px RGBA master 与完整 iconset，再调用 macOS `iconutil`。不提交派生 `.icns`，也不依赖 Downloads 路径。

### 9.4 验收原则

```text
[x] 用户确认最终图标方向 / asset 后才实施
[x] 正式 build 不依赖开发机外部绝对路径
[x] packaged App 的 `CFBundleIconFile` 指向有效 1024 px RGBA ICNS（Finder / Dock 标准解析合同）
[x] icon asset 进入 repo 中正式可重建 packaging 路径
[x] formal build / codesign / packaged verifier 继续 PASS
[x] Release ZIP round-trip 后图标仍保留
```

具体 `.icns` 生成方式、源图格式、PyInstaller wiring 由 Codex 在该 Step 根据 packaging 现状选择最小正确实现。

建议 commit 语义：

```text
feat: add app icon
```

---

## 10. Step 1G - Packaged regression / acceptance

状态：**ACTIVE**；本次 1F 任务不实施 1G。

1A-F 全部经 GitHub 实际实现审核通过后执行一次整轮收口，不再顺手增加功能。

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
中文 / English UI switch
两套 UI 关键语义对齐
UI language 与 Original Language 分离
packaged App custom icon
Start -> real transcription -> Stop
Stop -> second Start
new timestamp session under chosen root
raw.txt / clean.txt / session.log / config.json evidence
repo worktree clean
```

Packaged regression 可在任一当前已验证的 Apple Silicon 开发机完成；普通 Product / UX 回归不按 M4 Max / M5 分配固定角色。

如果 1A-F 实际只触及 UI/settings/controller/packaging polish 层且所有 packaging / ASR regression PASS，不默认要求重复此前约 35 分钟课堂测试；若实现触碰 Runtime/ASR 冻结边界，则在 1G 前停止并升级验收。

1G PASS 后再由用户决定：

```text
是否发布新 GitHub Release
是否恢复 llm-sidecar-phase1
是否开启新的 Product / UX Step
```

---

## 11. 明确不进入 Step 1 的项目

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

## 12. 当前 ACTIVE / Historical overnight execution

当前唯一 ACTIVE 是 **Step 1G - Packaged regression / acceptance**。1C -> 1E overnight batch 与用户随后明确授权的 1F 均已完成；本节保留原 batch 事实供审计，不再作为执行 1C-1F 的授权。

开始前必读：

```text
docs/product_polish_static.md
docs/product_polish_runtime.md
docs/repo_map.md
docs/deployment_static.md
README.md
```

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

### 12.1 Historical overnight batch（完成）

用户已明确授权：

```text
1C
-> 相关 tests + full reasonable regression
-> 独立 commit
-> push main
-> gate PASS

1D
-> 重新基于当前 HEAD 审计
-> 相关 tests + full reasonable regression
-> 独立 commit
-> push main
-> gate PASS

1E
-> 重新基于当前 HEAD 审计
-> 相关 tests + full reasonable regression
-> 独立 commit
-> push main
-> gate PASS
```

任何 gate FAIL、contract 不清楚、需要触碰 stable ASR/evidence/integrity 冻结边界、或 origin/main 出现无法解释的新推进：

```text
STOP ENTIRE BATCH
```

不得跳过失败 Step 继续后面的 Step。

Codex 在 batch 中仍不得修改：

```text
docs/product_polish_static.md
docs/product_polish_runtime.md
docs/repo_map.md
docs/deployment_static.md
docs/deployment_runtime.md
```

每个 Step 最终都必须单独报告：

```text
changed files
tests
commit SHA
push result
Repo Map impact: NONE / UPDATE REQUIRED
```

### 12.2 Batch 完成后的 automated pre-1G regression

1C、1D、1E 三个 gate 已全部 PASS 并分别 push；其后的 automated pre-1G regression 只作为历史验证证据：

```text
full relevant unit / contract regression
formal one-entry build（若当前正式 build prerequisites 可满足）
packaged Runtime verifier
```

目的仅是提前暴露 packaging/runtime regression，节省后续人工等待。

这一步：

```text
不产生功能 commit
不修改 packaging 来“顺手修”失败
不标记 1G PASS
不做 GitHub Release/tag
```

如果 formal build / verifier 失败，保留证据并汇报；不要为了让 overnight batch 看起来成功而扩大 scope。

### 12.3 明确停止点

Overnight batch 已在以下边界结束：

```text
1E implementation pushed
+ optional automated pre-1G regression report
```

当前 1F 已根据后续用户明确授权独立完成。下一次只允许在新的明确任务中执行：

```text
1G final acceptance
release/tag
```

---

## 13. 上下文恢复入口

Product / UX Step 1：

```text
1. docs/product_polish_static.md
2. docs/product_polish_runtime.md
3. docs/repo_map.md
4. docs/deployment_static.md
5. docs/deployment_runtime.md
6. README.md
7. ui_app.py
8. model_manager.py
9. settings.py
10. resource_paths.py
11. transcription_controller.py（1D 重点）
12. transcript_store.py（合同参考，默认避免修改）
13. packaging/ClassroomTranscriber.spec（1F 重点）
14. 相关 testCodes/
```

Release / Deployment 历史继续由 `docs/deployment_runtime.md` 保存；不要把 Product / UX Step 1 的 ACTIVE 状态写回 LLM runtime。
