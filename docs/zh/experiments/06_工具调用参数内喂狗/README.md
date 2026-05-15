## 实验六：工具调用参数内喂狗 —— 方案可行性证伪与"注意力分配冲突"现象

**目的：** 验证 AgentPreproxy 看门狗能否扩展到工具调用 (`function calling`) 场景。具体方案是让模型在 tool 参数的字符串值内部自插 `<wd:N>` 标签，看门狗实时解析。本实验对该方案做端到端实测，结果**部分证伪原方案前提**，并暴露一个比"注意力塌陷"更前置的现象——**注意力分配冲突**。

---

### 一、背景

主论文（[`docs/zh/paper/主论文.md`](../../paper/主论文.md)）提出看门狗探针在 streaming 文本流上工作。但在工具调用场景下，注意力可能塌陷在两个新位置：

1. **thinking 阶段**：reasoning_content 流不喂狗，是完全盲区
2. **tool 参数生成阶段**：`function.arguments` 是 partial JSON delta 流，看门狗的 numeric/structural/behavioral 三层探针无法直接套用（JSON 本身就有大量括号）

候选方案是"参数内喂狗"：通过 system prompt 让模型在 args 字符串值里每约 10 词插一个 `<wd:N>` 标签，看门狗对该标签流跑 numeric + structural 探针。理论支撑：grammar-constrained sampling 不约束字符串值的内容，标签可以合法穿过。

实验目的就是验证这套方案的三个未知前提。

---

### 二、实验方法

- **模型：** `qwen3.6-27b`（LM Studio，OpenAI 兼容 API，`192.168.3.25:1234`）
- **脚本：** [`probe_tool_args.py`](probe_tool_args.py)（stdlib only，无第三方依赖）
- **工具：** 单一 `file_write({path, content})`，要求模型把生成内容写入文件
- **指令变体（6 种注入位置/措辞）：**
  - `sys_only`：约定写在 system prompt
  - `user_head` / `user_tail`：约定加在 user message 头部 / 尾部
  - `domain`：用"下游解析器要求"的语义包装
  - `noplan_user` / `noplan_sys`：显式禁止 thinking 阶段预规划
- **任务规模（3 种）：**
  - `short`：写 150 词 Rust ownership 介绍
  - `long`：写 600 词 Rust async 运行时对比
  - `stress`：写 80 项强模板 looper（与实验一同源压力源）
- **流式实时探针：** 解析累积的 `function.arguments` 字符串，提取 `<wd:N>` 出现位置/数字/闭合符状态

完整运行参数见脚本，原始结果落 [`results/`](results/)。

---

### 三、实测矩阵

| variant | case | thinking | tag 数 | 单调 | malformed | json | 判定 |
|---------|------|---------|-------|------|-----------|------|------|
| `sys_only` | short | T | 0 | – | 0 | ok | ❌ 完全无视指令 |
| `user_head` | short | T | 13 | +1 严格 | 0 | ok | ✅ 完美 |
| `user_head` | long (3000 max_tok) | T | 0 | – | – | – | ❌ thinking 1563c 后撞 max_tokens |
| `user_head` | long (32000 max_tok) | T | **1** | – | 0 | ok | ⚠ **指令遵从塌陷**：开头插 1 个就放弃 |
| `user_head` | short | F | 0 | – | – | – | ❌ thinking 反而更失控 (3809c) |
| `domain` | short | T | 0 | – | – | – | ❌ "下游 reject" 触发过度思考 |
| `user_tail` | short | T | 0 | – | – | – | ❌ thinking 4540c 撞墙 |
| `noplan_user` | short | T | 6 | +1 严格 | **18** | ok | ⚠ 闭合符漂移 `>` → `]` |
| **`noplan_user`** | **long (6000 max_tok)** | **T** | **28** | **+1 严格** | **0** | **ok** | **✅ 9044 args 健康** |
| `noplan_user` | stress (6000 / 32000) | T | – | – | – | – | ❌ LM Studio routing 崩，args=空 |

完整原始数据：[`results/`](results/) 11 份 JSON。

---

### 四、三个前提的验证结果

| 前提 | 结论 | 证据 |
|------|------|------|
| **P1** 27B 服从插 tag 指令 | ⚠ **条件性成立** | `sys_only` / `domain` / `user_tail` 完全失败；只有 `user_head` 或 `noplan_user` 措辞且**注入到 user prompt** 才成立 |
| **P2** grammar/JSON schema 不拦字符串值内 tag | ✅ **完全成立** | 所有成功 case 的 `<wd:N>` 都精准落在 `content` 字段字符串值内，path 字段无污染，JSON 始终合法可解析 |
| **P3** 塌陷时 tag 退化清晰 | ⚠ **部分成立** | `noplan_user/short` 实测到 `>` → `]` 闭合符漂移：数字层不动、结构层能抓。与 [实验一 Gemma 4 e2b 的格式塌陷](../01_基础能力测试/) 同源。**但** `user_head/long@32k` 暴露了"指令遵从塌陷"——模型主动放弃 tag 指令，看门狗彻底失去信号。 |

---

### 五、核心新发现：注意力分配冲突 ≠ 注意力塌陷

这是本实验最重要的理论贡献。

#### 5.1 现象

`user_head/long` 在不限 max_tokens 时跑出来：
- args 长度 19471 chars，连贯的 Rust async 运行时技术文章
- thinking 2109 chars，正常推理
- JSON 完整可解析
- **但只有 1 个 `<wd:1>` tag，全在开头**

模型主任务（写文章）执行得**很好**，仅仅是 wd tag 这条副指令在生成中途被丢了。

#### 5.2 与主论文定义对照

[主论文](../../paper/主论文.md) 严格框定"注意力塌陷"为：
> 失控重复 ≡ 注意力涣散，两者是同一事件的内外两面。

按这个定义判：
- ❌ **不是失控重复** —— 19471 chars 是连贯文章，无重复
- ❌ **不是格式塌陷** —— JSON 合法、内容质量正常
- ❌ **没有自指闭锁** —— 模型注意力在主任务上完全在线
- ⚠ **只是 tag 这条副指令在生成中被裁剪了**

更准确的描述是 **注意力资源争抢 / 分配冲突**：模型的注意力预算被"写好一篇技术文章"主任务占满，wd tag 计数副指令在 thinking 阶段被裁剪。

比喻：
- 真塌陷 = 司机睡着方向盘乱打（注意力消失）
- 这次实测 = 司机专心看导航没盯后视镜（注意力都在主任务上，副任务被牺牲）

#### 5.3 与实验一 (gemma-4-e2b looper) 的对照

[实验一](../01_基础能力测试/) 的 watchdog v0 在 looper prompt（强模板填空）下观察到：
- 数字单调始终成立
- `<wd:N` 缺 `>`、字段名消失 — 注意力**资源耗尽**的外显
- 损坏间隔 10→9→9→4→6 缩短 — 真塌陷的加速

实验一看到的是"模型还在尝试维持模板但维持不动了"——**真塌陷的前驱**。
本实验看到的是"模型主动放弃了 tag 指令"——**主动取舍**。

两个现象表面相似（tag 异常），机制完全不同。

#### 5.4 对原方案的根本打击

参数内喂狗方案的**理论基础是预设"模型会一直试图维持 tag"**。这个预设：

| 场景 | 是否成立 | 原因 |
|------|---------|------|
| 实验一 looper prompt（强模板） | ✅ 成立 | tag 在模板里，是任务的一部分 |
| 本实验自由写作 args | ❌ 不成立 | tag 是元约束，模型可裁剪 |

更糟的是，watchdog 报警时**根本分不清**：
| 情形 | tag 状态 | 注意力状态 |
|------|---------|------------|
| 注意力健康 + 主任务轻 | 有 tag 单调 | 健康 |
| 注意力健康 + 主任务重 | tag 消失 | **健康但被挤占** |
| 真塌陷（失控重复） | tag 消失或乱跳 | 涣散 |

后两行 tag 表现相同，看门狗看不出区别。在生产场景（长 file_write）下大概率永远是"太忙"，永远报警，等于狼来了。

---

### 六、对原方案的工程评估

实测把方案的可用区间压缩到了"中等长度 args（200-1000 词）+ `noplan_user` 措辞 + 容忍 `]` 偷工误报"。但生产里写代码的 file_write 主要是长 args 场景，正好落在**方案失效区**（指令遵从塌陷）。

如果坚持集成，需要：

1. **指令传递机制要改**：不能放 system prompt（27B 完全无视）。需要每次发请求前向 messages 尾追加一条 transient guidance message。该消息**不能进入持久化对话历史**，仅用于本次请求。
2. **看门狗要分级**：把"闭合符漂移"判 Mild、"数字非单调或长段无 tag"才判 Severe。
3. **必须接受**：长 args 上 watchdog 是盲的（指令遵从塌陷），**不要假装它有用**。
4. **每次 tool call 多消耗** ~500-1000 thinking token + 5-8% output token。

#### 替代方向（未验证）

1. **客户端被动监控**：不依赖模型自报，监控 chunk 间隔、生成速率、JSON 结构进度（深度变化、字段闭合速度）。属于真正"注意力之外"的信号。
2. **thinking 阶段单独探针**：reasoning_content 流今天完全无监控，是更大的盲区。
3. **完全放弃工具调用场景看门狗，专注文本流**：承认工具调用是不同问题，需要另一套 spec。

---

### 七、复现说明

```bash
cd docs/zh/experiments/06_工具调用参数内喂狗
python3 probe_tool_args.py --case <short|long|stress|all> --variant <sys_only|user_head|user_tail|domain|noplan_user|noplan_sys> [--no-thinking] [--max-tokens-override N]
```

需要在 `probe_tool_args.py` 顶部修改 `API_URL` 和 `MODEL` 指向自己的 LM Studio 端点。

依赖：仅 Python stdlib。

---

### 八、相关文档

- [实验一 基础能力测试](../01_基础能力测试/) — 看门狗 v0 在 gemma-4-e2b 上的格式塌陷发现，与本实验形成对照
- [实验四 误杀对比](../04_误杀对比/) — 看门狗在文本流上的零误杀数据
- [主论文](../../paper/主论文.md) — "注意力塌陷"的严格定义与自指闭锁论证
- [《实现_看门狗与计数Tag》](../../paper/实现_看门狗与计数Tag.md) — 计数 tag 看门狗的工程说明（本实验是其在工具调用场景的扩展尝试）

---

**实验日期：** 2026-05-15  
**外部触发项目：** [GrowBox](https://github.com/) 的看门狗集成需求 — GrowBox 拟在工具调用 streaming 流上接入 AgentPreproxy 看门狗，本实验是该集成前的可行性验证。结论：**该集成方案不推荐，原方案对工具调用场景的扩展存在结构性问题。**
