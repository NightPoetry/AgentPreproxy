# AgentPreproxy

**AI Attention Watchdog — Detect and intervene when LLMs lose control.**

[中文](#agentpreproxy-中文) | [English](#agentpreproxy-english)

---

<a id="agentpreproxy-english"></a>

## What is this?

AgentPreproxy is a local proxy that sits between your AI agent software and the LLM API. It solves a structural problem that no amount of compute can fix:

> **When a model enters runaway repetition, its attention has already collapsed — it cannot detect the problem from inside. This is a logical deadlock, not an engineering limitation.**

The proxy uses a **counting Tag watchdog**: the model outputs incrementing Tags (`⟪WD:1⟫`, `⟪WD:2⟫`, ...) as an attention heartbeat. When Tags break → intervene. When Tags are correct → let it through, even during repetitive content.

**Result:** 0-8% false positive rate vs 46-50% for naive truncation.

## Quick Start

### 1. Install

```bash
git clone https://github.com/yourname/AgentPreproxy.git
cd AgentPreproxy
pip install -e .
```

Requires Python 3.11+.

### 2. Start the proxy

**OpenAI API:**
```bash
python run.py \
  --port 8600 \
  --openai-url https://api.openai.com \
  --openai-key sk-xxxxxxxx \
  --mode both \
  --debug
```

**Anthropic API:**
```bash
python run.py \
  --port 8600 \
  --anthropic-url https://api.anthropic.com \
  --anthropic-key sk-ant-xxxxxxxx \
  --mode both \
  --debug
```

**Local model (LM Studio / Ollama / vLLM):**
```bash
python run.py \
  --port 8600 \
  --openai-url http://localhost:1234/v1 \
  --mode strong \
  --debug
```

### 3. Point your agent software to the proxy

Change one line in your agent's config — replace the real API URL with:

```
http://127.0.0.1:8600
```

That's it. The proxy is transparent — same API format, same request/response structure. Your agent software doesn't know it's there.

**Example with curl:**
```bash
curl http://127.0.0.1:8600/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

**Example with Python (openai SDK):**
```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8600/v1", api_key="sk-xxx")
resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "Hello!"}])
```

### 4. Monitor (debug mode)

When started with `--debug`, the proxy exposes monitoring endpoints:

```bash
# View active request states
curl http://127.0.0.1:8600/debug/state

# View runtime config
curl http://127.0.0.1:8600/debug/config

# View stats (tag hits, interventions, etc.)
curl http://127.0.0.1:8600/debug/stats

# Change config at runtime (e.g. switch watchdog mode)
curl -X POST http://127.0.0.1:8600/debug/config \
  -H "Content-Type: application/json" \
  -d '{"watchdog_mode": "strong", "strong_k": 30}'
```

## All Parameters

```
python run.py --help

Options:
  --host          Listen address          (default: 127.0.0.1)
  --port          Listen port             (default: 8600)
  --openai-url    Upstream OpenAI API     (default: https://api.openai.com)
  --openai-key    OpenAI API key
  --anthropic-url Upstream Anthropic API  (default: https://api.anthropic.com)
  --anthropic-key Anthropic API key
  --mode          Watchdog mode: strong | weak | both | off  (default: both)
  --strong-k      Words between Tags      (default: 50)
  --debug         Enable debug endpoints + verbose logging
  --log-level     Log level               (default: INFO)
```

**Watchdog Modes:**

| Mode | Behavior | Use Case |
|------|----------|----------|
| `strong` | Tag every K words, always-on monitoring | Maximum safety, slight token overhead |
| `weak` | Tags only required during repetition | Minimal overhead, relies on repetition detector |
| `both` | Strong + weak combined | Recommended default |
| `off` | Pure transparent proxy, no watchdog | Testing / bypass |

## How It Works

```
Your Agent Software                AgentPreproxy                    Real LLM API
       │                                │                               │
       ├──── request ──────────────────>│                               │
       │                    escape Tags │                               │
       │                    inject rules│                               │
       │                                ├──── modified request ────────>│
       │                                │                               │
       │                                │<──── response with Tags ──────┤
       │                    parse Tags  │                               │
       │                    watchdog ✓? │                               │
       │                    strip Tags  │                               │
       │<──── clean response ───────────┤                               │
       │                                │                               │
       │   (user never sees Tags)       │   (model outputs Tags)        │
```

**Auto-detection:** The proxy detects OpenAI (`/v1/chat/completions`) vs Anthropic (`/v1/messages`) format from the request path. No configuration needed.

**Streaming:** Fully supported. Tags are parsed and stripped in real-time from the SSE stream.

## Key Experimental Findings

| Metric | Naive Truncation | Watchdog |
|--------|-----------------|----------|
| False positive rate (9B) | 46% | **0%** |
| False positive rate (e2b) | 50% | **8%** |
| 1B model runaway (50x request) | 282 actual | Tag-detectable |
| 1B LoRA internalization | — | WD:1→7, then degrades |

See full reports: [English](docs/en/) | [中文](docs/zh/)

## Project Structure

```
AgentPreproxy/
├── docs/
│   ├── zh/              # 中文文档、论文、实验数据
│   │   ├── paper/       # 主论文 + 机制分类 + 实现 + 透明性 + 口播
│   │   └── experiments/ # 5组实验 + 总报告 + 可视化HTML
│   └── en/              # English papers + experiment reports + HTML
├── src/
│   ├── agentpreproxy/   # Proxy source code
│   │   ├── proxy/       # Server, adapters (OpenAI/Anthropic), escape, inject, stream
│   │   ├── core/        # Tag parser, watchdog, repetition detector, intervention
│   │   └── debug/       # Logger, hooks, /debug/* endpoints
│   └── tests/           # 30 unit tests (pytest)
├── README.md            # This file
├── LICENSE              # Apache 2.0
├── pyproject.toml
└── run.py               # Entry point
```

## License

[Apache License 2.0](LICENSE)

---

<a id="agentpreproxy-中文"></a>

# AgentPreproxy 中文

**AI 注意力看门狗 — 检测并介入大模型的失控重复。**

## 这是什么？

AgentPreproxy 是一个本地代理，插在你的智能体软件和 LLM API 之间。它解决的是一个再强的算力都解决不了的结构性问题：

> **当模型进入失控重复时，它的注意力已经塌了——从内部根本感知不到这个问题。这是一个逻辑死锁，不是工程限制。**

代理使用**计数 Tag 看门狗**：模型输出递增 Tag（`⟪WD:1⟫`、`⟪WD:2⟫`...）作为注意力心跳。Tag 断裂 → 介入。Tag 正确 → 放行（哪怕内容在重复）。

**结果：** 看门狗误杀率 0-8%，直接截断误杀率 46-50%。

## 快速开始

### 1. 安装

```bash
git clone https://github.com/yourname/AgentPreproxy.git
cd AgentPreproxy
pip install -e .
```

需要 Python 3.11+。

### 2. 启动代理

**接 OpenAI API：**
```bash
python run.py \
  --port 8600 \
  --openai-url https://api.openai.com \
  --openai-key sk-xxxxxxxx \
  --mode both \
  --debug
```

**接本地模型（LM Studio / Ollama / vLLM）：**
```bash
python run.py \
  --port 8600 \
  --openai-url http://localhost:1234/v1 \
  --mode strong \
  --debug
```

### 3. 指向代理

把智能体软件的 API 地址改成：

```
http://127.0.0.1:8600
```

完了。代理是透明的——API 格式不变、请求响应结构不变。你的智能体软件感觉不到它的存在。

**curl 示例：**
```bash
curl http://127.0.0.1:8600/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o", "messages": [{"role": "user", "content": "你好"}]}'
```

**Python (openai SDK) 示例：**
```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8600/v1", api_key="sk-xxx")
resp = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":"你好"}])
```

### 4. 监控（调试模式）

用 `--debug` 启动后有监控端点：

```bash
curl http://127.0.0.1:8600/debug/state   # 查看活跃请求状态
curl http://127.0.0.1:8600/debug/config   # 查看运行时配置
curl http://127.0.0.1:8600/debug/stats    # 查看统计（Tag 命中率、介入次数等）

# 运行时修改配置
curl -X POST http://127.0.0.1:8600/debug/config \
  -H "Content-Type: application/json" \
  -d '{"watchdog_mode": "strong", "strong_k": 30}'
```

## 全部参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--host` | 监听地址 | 127.0.0.1 |
| `--port` | 监听端口 | 8600 |
| `--openai-url` | 上游 OpenAI API 地址 | https://api.openai.com |
| `--openai-key` | OpenAI API Key | — |
| `--anthropic-url` | 上游 Anthropic API 地址 | https://api.anthropic.com |
| `--anthropic-key` | Anthropic API Key | — |
| `--mode` | 看门狗模式：strong / weak / both / off | both |
| `--strong-k` | 强模式每隔多少词一个 Tag | 50 |
| `--debug` | 启用调试端点 + 详细日志 | 关 |
| `--log-level` | 日志级别 | INFO |

**看门狗模式说明：**

| 模式 | 行为 | 适用场景 |
|------|------|---------|
| `strong` | 每 K 词一个 Tag，常态监控 | 最大安全性，有少量 token 开销 |
| `weak` | 只在重复出现时要求 Tag | 最小开销，依赖重复检测器 |
| `both` | 强 + 弱结合 | 推荐默认 |
| `off` | 纯透传代理，不启用看门狗 | 测试 / 旁路 |

## 工作原理

```
你的智能体软件              AgentPreproxy                    真实 LLM API
     │                           │                               │
     ├──── 请求 ────────────────>│                               │
     │                 转义 Tag  │                               │
     │                 注入规则  │                               │
     │                           ├──── 修改后的请求 ────────────>│
     │                           │                               │
     │                           │<──── 带 Tag 的响应 ───────────┤
     │                 解析 Tag  │                               │
     │                 看门狗 ✓? │                               │
     │                 去掉 Tag  │                               │
     │<──── 干净的响应 ──────────┤                               │
     │                           │                               │
     │  （用户看不到 Tag）        │  （模型输出 Tag）              │
```

**自动识别：** 代理根据请求路径自动识别 OpenAI（`/v1/chat/completions`）和 Anthropic（`/v1/messages`）格式，无需配置。

**流式支持：** 完整支持。Tag 在 SSE 流中实时解析和去除。

## 协议

[Apache License 2.0](LICENSE)

## 文档

- [中文论文 + 实验报告](docs/zh/)
- [English papers + experiments](docs/en/)
