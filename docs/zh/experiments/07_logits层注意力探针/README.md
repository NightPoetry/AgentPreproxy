## 实验七：Logits 层注意力探针 ——「在注意力之外」的探针落地

> **状态：** 设计完成，待执行。下个会话的执行者请按本文档操作。
>
> **执行难度：** 中等。涉及取舍，但路径已铺。卡住时回到 §5 决策树。

---

### 一、上下文（必读，5 分钟）

#### 1.1 这份文档的来源

[实验六](../06_工具调用参数内喂狗/) 证伪了"通过 prompt 让模型在 tool 参数里自插 `<wd:N>` 标签"的方案。最重要的发现是 **「指令遵从塌陷」**：模型在长 args 上**主动放弃**副指令（比如 wd tag），并不是真塌陷，但看门狗会被骗。结论：

> **任何依赖模型自愿遵从的探针，在生产场景都会被注意力分配挤掉。**

实验七要落地真正"在注意力之外"的探针。

#### 1.2 两个候选方案

| 方案 | 思路 | 优势 | 风险 |
|------|------|------|------|
| **D（主）** | 监控每个 token 的采样器内部状态（entropy、top-k 集中度、surprise 等），不依赖模型输出任何标签 | 真旁路、与主论文"自指闭锁"论证天然对齐 | 信号是否真有区分力**未验证** |
| **B（备）** | 采样器每 K token 强制开 `<wd:`，N 由模型采。N 的单调性是探针信号 | 副任务极致简化（只填一个数字），分配冲突大概率绕过 | 仍然在用模型预测，理论纯度不如 D |

**策略：** 先做 D。D 不成立才退到 B。如果 B 也不成立，记录"两路线均失败"是有价值的负结果。

#### 1.3 已有相关工作（节省你研究时间）

- **mirostat**（Basu et al. 2020，已集成 llama.cpp 主线 5 年）：实时监控 token surprise + 反馈调温度。**是 D 路线的成品但目的不同**（维持文本质量，不报警）。直接读 mirostat 源码学如何在采样器里取 logits。
- **hallucination detection 学术**：用 entropy / semantic entropy（Farquhar et al. 2024 Nature）。目标不是塌陷探针，但 entropy 计算公式可以借用。
- **AgentPreproxy 现有探针**：numeric/structural/behavioral 三层（[实验一](../01_基础能力测试/)），都在输出层。

D 的真正空白 —— **没人把 logits 特征跟"失控重复 ≡ 注意力涣散"这个故障模式对齐做过实验。**

---

### 二、技术栈选型

#### 2.1 推理后端

| 后端 | 优点 | 缺点 | 推荐 |
|------|------|------|------|
| `llama-cpp-python` | Python 原生、`LogitsProcessor` 简单、Mac/Linux 通吃 | 性能一般 | ✅ **首选** |
| `vLLM` | 高性能、生产级 | 装环境麻烦、Mac 不支持 | 备选（如 llama-cpp 太慢） |
| `sglang` | 高性能 | 生态新 | 暂不考虑 |
| `mlx-lm` | Mac 原生快 | LogitsProcessor 接口不稳 | 暂不考虑 |

**默认用 `llama-cpp-python`**。如果 7B 跑都嫌慢，再考虑切 vLLM。

#### 2.2 模型

用 **Qwen3.6-27B（Q4_K_M GGUF）**，跟实验一/六同源。

如果机器吃不下 27B（VRAM < 16GB 且 RAM < 24GB），退到 **Qwen2.5-7B-Instruct（Q4_K_M）** 验证可行性。**注意：7B 上的塌陷模式与 27B 可能不同**，最终结论必须在 27B 上复现。

#### 2.3 安装

```bash
# Mac (Apple Silicon, Metal 加速)
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python

# Linux + CUDA
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python

# 模型下载（用 huggingface-cli 或直接 wget GGUF 链接）
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-GGUF qwen2.5-7b-instruct-q4_k_m.gguf --local-dir ./models
```

如果 27B GGUF 找不到，可以用 [bartowski](https://huggingface.co/bartowski) 的量化版本。

---

### 三、D 方案：详细工程指引

#### 3.1 取 logits 数据 —— 最小例子

```python
from llama_cpp import Llama
import numpy as np

def softmax(x):
    e = np.exp(x - x.max())
    return e / e.sum()

class WatchdogLogitsProbe:
    """每步采样前回调,计算并记录 logits 特征,不修改采样。"""
    def __init__(self):
        self.records = []  # 每个 token 一条记录

    def __call__(self, input_ids, scores):
        # input_ids: list[int],已生成的 token id 序列
        # scores:    np.ndarray (vocab_size,) 当前步的 raw logits
        probs = softmax(scores)
        # 关键四个特征
        entropy = float(-(probs * np.log(probs + 1e-12)).sum())
        max_p = float(probs.max())
        # top-10 集中度:前 10 个最大概率的总和
        top10 = np.partition(probs, -10)[-10:]
        top10_concentration = float(top10.sum())
        # surprise = -log p(实际采到的 token);需在采样后回填,这里先占位
        self.records.append({
            "step": len(self.records),
            "entropy": entropy,
            "max_p": max_p,
            "top10_concentration": top10_concentration,
        })
        return scores  # 透传,不改采样

probe = WatchdogLogitsProbe()
llm = Llama(
    model_path="./models/qwen2.5-7b-instruct-q4_k_m.gguf",
    n_gpu_layers=-1,    # Metal/CUDA offload 全部层
    n_ctx=8192,
    verbose=False,
)
out = llm("...你的 prompt...", max_tokens=4000, temperature=0.7,
          logits_processor=[probe])
text = out["choices"][0]["text"]
# 现在 probe.records 是逐 token 特征序列,长度 = 生成 token 数
```

**回填 surprise（采样之后的特征）：**

`LogitsProcessor` 在采样**前**调用，所以拿不到"实际采到哪个 token"。要 surprise 的话，可以在采样**后**通过 `out["choices"][0]["logprobs"]` 拿 token-level logprob（需要 `logprobs=True`）。或更简单：把 surprise 算法写成"事后从 records 和实际 token 序列对齐"。**初版可以不要 surprise，只要 entropy/max_p/top10 三个特征**，看够不够区分。

#### 3.2 实验设计

**必跑的 case：**

| case | prompt 来源 | 期望 |
|------|-----------|------|
| **C1** looper-100 | 同 [实验一](../01_基础能力测试/) 的 looper（"输出 100 个不同 COLOR 苹果的描述..."） | 27B 上是否会塌陷未知,先试 |
| **C2** looper-200 | 加压到 200 项 | 27B 大概率会塌 |
| **C3** 自由写作（控制） | "写 600 字关于 Rust 异步运行时的对比"  | 期望不塌,作 baseline |
| **C4** 工具 args 长生成 | 让模型写 600 字技术文章到文件,通过 chat-template 模拟 tool call（llama-cpp-python 不直连 tool API） | 探测 tool 场景下 logits 是否有特殊模式 |

**采样配置：** temperature=0.7、top_p=0.95、不设 `seed`（每次新随机）。每个 case 跑 **5 次**。

**采集字段（逐 token）：**
- `entropy`、`max_p`、`top10_concentration`
- 可选：`surprise`（事后回填）、`top1_token_id`（用于事后定位重复）

#### 3.3 分析方法

对每个 case 的每次跑：

1. **判定塌陷起点：** 人工或自动扫文本，找：
   - 第一次出现重复 4-gram 的位置（用滑窗）
   - 第一次出现格式破损（缺闭合、缺关键字段）
   - 取较早者作为「塌陷点 token 索引 t*」
2. **对齐：** 取 `[t*-50, t*-1]` 作为「塌陷前段」，取 `[t*+10, t*+60]` 作为「塌陷后段」（跳过临界 10 tokens 减少噪声）。再从 case 早期取 `[100, 200]` 作为「健康段」。
3. **比较：** 对每个特征 X ∈ {entropy, max_p, top10_concentration}，算：
   - `mean(X | 塌陷前)` - `mean(X | 健康段)`
   - `mean(X | 塌陷后)` - `mean(X | 健康段)`
   - 效应量（Cohen's d 或 KS 距离）
4. **跨 5 次实验聚合：** 看方向一致性。如果 5/5 都是「塌陷前 entropy 下降」，信号成立。

**期望结果（猜想，不是结论）：**
- entropy 在塌陷前**下降**（模型分布塌缩成「再说一遍」的高确定性）
- top10_concentration **上升**
- max_p **上升**

如果观察到这些，且 C3（控制）不出现，**D 成立**。

#### 3.4 输出物

照实验四/六风格组织：

```
docs/zh/experiments/07_logits层注意力探针/
├── README.md           ← 已存在(本文档),实验完成后追加「八、实施记录」节
├── probe_logits.py     ← 主脚本(你写)
├── analyze.py          ← 分析脚本(你写)
├── results/            ← raw JSON × ~20 (4 case × 5 runs)
│   ├── 20260516TXXXXXX_C1_run1.json
│   └── ...
└── plots/              ← entropy 曲线图(matplotlib 即可)
    ├── C1_entropy.png
    └── ...
docs/en/experiments/07_logits_layer_probe/
└── README.md           ← 英文摘要(指向中文版)
```

#### 3.5 验收标准（D 成立的硬指标）

全部满足才算 D 成立：

- [ ] **C2 looper-200** 5 次中至少 4 次出现塌陷
- [ ] 在出现塌陷的运行里，至少**一个特征 X**满足：「塌陷前段」与「健康段」的均值差，方向在 5 次中**完全一致**（5/5 同号）
- [ ] 该差异的 Cohen's d > 0.5（中等效应量）或 KS 距离 > 0.2
- [ ] **C3 控制** 上同一特征**不**出现同方向同幅度变化（避免误报）
- [ ] 整套探针每 token 额外开销 < 1ms（用 `time.perf_counter()` 测）

满足 → 写「八、实施记录」节，commit + push，回 GrowBox 写薄交接「D 成立，可启动 AgentPreproxy 主项目集成讨论」。

---

### 四、B 方案（备用）

D 验收**任一项**不满足 → 启动 B。

#### 4.1 触发条件（明确）

- 所有特征在塌陷点**没有**显著变化（D 失效）
- OR 信号在 C3 控制上也出现（误报）
- OR 跑不出来塌陷（C2 上 5 次都没塌）

#### 4.2 实现思路

复用同一份 `LogitsProcessor` 框架，加一个 `enforce_wd_frame_every_k` 参数：

```python
class WdFrameEnforcer:
    """每 K tokens 强制开 <wd: 框架,N 让模型自己采。"""
    def __init__(self, llm: Llama, k: int = 20):
        self.llm = llm
        self.k = k
        self.token_count = 0
        self.in_wd_frame = False  # 是否正在被强制写 <wd:
        # 预计算 token id
        self.LT = llm.tokenize(b"<", add_bos=False)[0]      # `<`
        self.WD = llm.tokenize(b"wd:", add_bos=False)       # `wd:` 可能多 token
        # ... 详见 llama-cpp-python tokenize 文档

    def __call__(self, input_ids, scores):
        self.token_count += 1
        # 简化版:每 K tokens,把所有非 `<` 起始的 token logits 设 -inf
        if self.token_count % self.k == 0 and not self.in_wd_frame:
            mask = np.full_like(scores, -np.inf)
            mask[self.LT] = scores[self.LT]
            self.in_wd_frame = True
            return mask
        # ... 然后强制 `wd:`,然后让模型采 N,然后强制 `>`,然后释放
        return scores
```

**关键陷阱：**
- `<`、`wd:`、数字、`>` 在 BPE tokenizer 里**未必是单 token**。要先 `llm.tokenize(b"<wd:1>")` 看实际 token 序列，再设计强制逻辑。可能需要用状态机：阶段 0=自由生成、阶段 1=强制 `<`、阶段 2=强制 `wd:`、阶段 3=自由采 N、阶段 4=强制 `>`、回阶段 0。
- N 是多 digit 时（10、11、...），自由采阶段要识别"模型采到了非数字 token = 数字结束"。

完整实现预计 100-200 行 Python。建议先在 toy prompt 上把状态机跑通，再上 looper case。

#### 4.3 验收标准（B 成立）

- [ ] looper-200 上模型采 N 出现非单调（数字层信号成立）
- [ ] C3 控制上 N 始终单调（不误报）
- [ ] 强制 tag 框架不导致模型整体输出质量崩坏（手工读样本判定）

#### 4.4 B 也不成立的情况

写报告 **「两路线均失败」**，结论：

> 工具调用场景下，注意力探针存在原理性盲点：模型注意力可以在不输出任何可观测异常的前提下塌陷或被挤占。AgentPreproxy 范式不可直接扩展到工具调用场景。

这是有价值的负结果，照实写出来即可。

---

### 五、决策树（卡住时看这里）

```
开始
 ↓
跑 C1 (looper-100, 27B)
 ├ 5 次都没塌 → 加压到 C2 (looper-200)
 │   ├ 还是没塌 → 加压到 C2' (looper-500) 或换更小模型(7B)看能否复现塌陷
 │   │   ├ 能复现 → 用复现的 case 继续
 │   │   └ 还不行 → 写「27B 在 logits 探针实验中难以诱发塌陷」报告,转 B 方案直接试
 │   └ 塌了 → 进 §3.3 分析
 └ 塌了 → 进 §3.3 分析

§3.3 分析后
 ├ D 验收全过 → 写报告「D 成立」,完
 └ D 验收任一不过 → 进入 B 方案 §4
                      ↓
                     B 实现 + 验收
                      ├ B 验收全过 → 写报告「B 成立 D 不成立」,完
                      └ B 也不过 → 写「两路线均失败」报告,完
```

---

### 六、关键陷阱（实验六踩过的，别重蹈）

1. **27B 不要走 system prompt 注入：** Qwen3.6-27B 在 system prompt 里完全无视 wd 类指令。如果你需要写 prompt（比如 B 方案要不要给模型解释 `<wd:N>` 是什么），约定要放在 user message。
2. **enable_thinking 默认开：** Qwen3.6 关 thinking 反而 reasoning 阶段更失控。llama-cpp-python 的 chat template 里默认应该是开的，确认一下。
3. **绕开 LM Studio：** 实验六的 stress case 上 LM Studio routing 崩了。直接走 llama-cpp-python 不经过 OpenAI 兼容层。
4. **「注意力分配冲突 ≠ 注意力塌陷」：** 模型把副任务裁掉不算塌陷。判定塌陷必须看输出本身（重复、格式破损），不要凭 wd tag 消失就判塌陷。
5. **max_tokens 默认要给够：** 实验六里 3000 撞墙没看到真行为，给到 32000 才看到。这里建议直接给 8000 起步。
6. **数字单调不是核心信号：** [实验一](../01_基础能力测试/) 在 gemma-4-e2b 上发现数字层基本不触发，主要塌陷信号是结构层和行为层。所以 B 方案的"N 单调性"在 27B 上不一定有信号，要做好心理准备。

---

### 七、复现/启动命令

```bash
cd docs/zh/experiments/07_logits层注意力探针/
# 写 probe_logits.py(参考 §3.1 例子)
python3 probe_logits.py --case C1 --runs 5
python3 probe_logits.py --case C2 --runs 5
python3 probe_logits.py --case C3 --runs 5
python3 probe_logits.py --case C4 --runs 5
# 写 analyze.py(对齐塌陷点、算特征差)
python3 analyze.py --results results/ --out plots/
# 把分析结论追加到本 README 的「八、实施记录」节
```

---

### 八、实施记录

> **执行者填写。** 完成后追加：
> - 跑了哪些 case、各几次
> - D 验收逐项结果（5 个 checkbox 打勾或写为什么没过）
> - 如果走到 B：B 实现说明 + B 验收结果
> - 关键发现（哪个特征最有区分力？塌陷前的 logits 模式什么样？）
> - 总结：D 成立 / B 成立 / 两路线失败
> - 数据文件清单
> - 给 GrowBox 的回执（一两句）

---

### 九、相关文档

- [实验一 基础能力测试](../01_基础能力测试/) — 提供 looper prompt 和已知塌陷模式
- [实验六 工具调用参数内喂狗](../06_工具调用参数内喂狗/) — 本实验的"为什么不走自报路线"理由
- [主论文](../../paper/主论文.md) — "自指闭锁"论证，D 路线的理论基础
- [《实现_看门狗与计数Tag》](../../paper/实现_看门狗与计数Tag.md) — 现有看门狗的工程说明，分析时与 logits 信号对照

---

**设计日期：** 2026-05-15
**设计者：** Claude Opus 4.7（与人类讨论合作）
**预计执行工作量：** 主线 D 约 2-3 天（含模型下载/装环境/写脚本/跑实验/分析）；B 备用约 +2 天；总报告 +0.5 天。
