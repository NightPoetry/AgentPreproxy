#!/usr/bin/env python3
"""
AgentPreproxy 实验脚本
模型: Gemma 3 1B (4bit MLX) via LM Studio
"""

import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

BASE_URL = "http://<LM_STUDIO_HOST_A>:1234/v1"
MODEL = "MODEL = "google/gemma-4-e2b"
TAG_RE = re.compile(r"⟪WD:(\d+)⟫")
OUTPUT_DIR = Path(__file__).parent / "results"


@dataclass
class ExperimentResult:
    name: str
    prompt: str
    system: str
    output: str
    duration: float
    token_count: int = 0
    tags_found: list[int] = field(default_factory=list)
    repetition_detected: bool = False
    repetition_ratio: float = 0.0
    notes: str = ""


def call_model(system: str, user: str, max_tokens: int = 1024, temperature: float = 0.7) -> tuple[str, float]:
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    })
    start = time.time()
    result = subprocess.run(
        ["curl", "-s", f"{BASE_URL}/chat/completions",
         "-H", "Content-Type: application/json",
         "-d", payload],
        capture_output=True, text=True, timeout=300,
    )
    elapsed = time.time() - start
    if result.returncode != 0:
        raise RuntimeError(f"curl failed: {result.stderr}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"bad response: {result.stdout[:200]}")
    if "error" in data:
        raise RuntimeError(f"API error: {data['error']}")
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return content, elapsed


def extract_tags(text: str) -> list[int]:
    return [int(m.group(1)) for m in TAG_RE.finditer(text)]


def detect_repetition(text: str, min_chunk: int = 30) -> tuple[bool, float]:
    if len(text) < min_chunk * 2:
        return False, 0.0
    for clen in range(min_chunk, min(len(text) // 2, 300)):
        tail = text[-clen:]
        preceding = text[-(clen * 2):-clen]
        if not preceding:
            continue
        if tail == preceding:
            return True, 1.0
        common = sum(1 for a, b in zip(tail, preceding) if a == b)
        sim = common / max(len(tail), 1)
        if sim > 0.85:
            return True, sim
    return False, 0.0


def run_experiment(name, system, user, max_tokens=1024, temperature=0.7):
    print(f"\n{'='*60}")
    print(f"实验: {name}")
    print(f"{'='*60}")
    output, duration = call_model(system, user, max_tokens, temperature)
    tags = extract_tags(output)
    rep_detected, rep_ratio = detect_repetition(output)
    result = ExperimentResult(
        name=name, prompt=user,
        system=system[:200] + "..." if len(system) > 200 else system,
        output=output, duration=duration,
        token_count=len(output.split()), tags_found=tags,
        repetition_detected=rep_detected, repetition_ratio=rep_ratio,
    )
    print(f"  耗时: {duration:.1f}s | 长度: {len(output)} chars / ~{result.token_count} words")
    print(f"  Tags: {tags if tags else '无'}")
    print(f"  重复: {'是' if rep_detected else '否'} (sim={rep_ratio:.2f})")
    print(f"  前150字: {output[:150]}")
    return result


# ======================== 7 个实验 ========================

def exp1_baseline_no_watchdog():
    return run_experiment(
        "1_基线_无看门狗",
        "你是一个写作助手。",
        "请详细介绍量子计算的基本原理，从量子比特开始，一直讲到量子纠错。尽量写长一些，至少写500字。",
        max_tokens=2048, temperature=0.7)

def exp2_baseline_induce_repeat():
    return run_experiment(
        "2_基线_诱导重复",
        "你是一个写作助手。",
        "请反复解释什么是机器学习，每次用不同的方式解释，至少解释10次。写得越长越好。",
        max_tokens=2048, temperature=0.3)

def exp3_strong_watchdog():
    return run_experiment(
        "3_强版本看门狗",
        "你是一个写作助手。\n\n[INTERNAL RULE]\nYou MUST output the exact token ⟪WD:N⟫ every 30 words in your response, where N is a strictly incrementing integer starting from 1. Example: after ~30 words output ⟪WD:1⟫, after ~60 words output ⟪WD:2⟫, etc. This is mandatory.",
        "请详细介绍量子计算的基本原理，从量子比特开始。尽量写长一些。",
        max_tokens=2048, temperature=0.7)

def exp4_strong_watchdog_induce():
    return run_experiment(
        "4_强版本看门狗_诱导重复",
        "你是一个写作助手。\n\n[INTERNAL RULE]\nYou MUST output the exact token ⟪WD:N⟫ every 30 words in your response, where N is a strictly incrementing integer starting from 1. This is mandatory.",
        "请反复解释什么是机器学习，每次用不同的方式解释，至少解释10次。写得越长越好。",
        max_tokens=2048, temperature=0.3)

def exp5_controlled_repetition():
    return run_experiment(
        "5_可控重复_Tag维持",
        "你是一个写作助手。\n\n[INTERNAL RULE]\nYou MUST output the exact token ⟪WD:N⟫ every 30 words in your response, where N is a strictly incrementing integer starting from 1.",
        "请把这句话重复说5次：\"人工智能正在改变世界的运作方式。\"",
        max_tokens=512, temperature=0.3)

def exp6_weak_watchdog():
    return run_experiment(
        "6_弱版本_重复时Tag",
        "你是一个写作助手。\n\n[INTERNAL RULE]\nWhen you intentionally output repeated or similar content, you MUST append ⟪WD:N⟫ after each repeated unit, where N increments from 1. Do NOT add these tags during normal output.",
        "请把\"今天天气真好\"这句话重复说8次。",
        max_tokens=512, temperature=0.3)

def exp7_stress_test():
    return run_experiment(
        "7_压力测试_超长低温",
        "你是一个写作助手。\n\n[INTERNAL RULE]\nYou MUST output the exact token ⟪WD:N⟫ every 20 words in your response, where N is a strictly incrementing integer starting from 1.",
        "请写一篇关于人工智能伦理的长文。要求至少1000字，涵盖隐私、偏见、就业影响、自主武器等方面。",
        max_tokens=2048, temperature=0.1)


def save_results(results):
    OUTPUT_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")

    lines = [
        f"# AgentPreproxy 实验报告",
        f"", f"- 模型: {MODEL} (4bit MLX, 736MB)", f"- 时间: {ts}", f"- 实验数量: {len(results)}",
        f"", f"## 汇总", f"",
        f"| # | 实验 | 输出长度 | Tags 数 | Tag序列 | 重复检测 | 耗时 |",
        f"|---|------|---------|--------|---------|---------|------|",
    ]
    for i, r in enumerate(results, 1):
        tag_cnt = len(r.tags_found)
        if r.tags_found:
            expected = list(range(r.tags_found[0], r.tags_found[0] + len(r.tags_found)))
            seq = "连续 ✓" if r.tags_found == expected else "断裂 ✗"
        else:
            seq = "无 Tag"
        rep = f"是 ({r.repetition_ratio:.0%})" if r.repetition_detected else "否"
        lines.append(f"| {i} | {r.name} | {len(r.output)} | {tag_cnt} | {seq} | {rep} | {r.duration:.1f}s |")

    lines += ["", "## 详细结果", ""]
    for r in results:
        lines.append(f"### {r.name}")
        lines.append(f"")
        lines.append(f"**Prompt:** {r.prompt}")
        lines.append(f"")
        lines.append(f"- 输出: {len(r.output)} chars / ~{r.token_count} words / {r.duration:.1f}s")
        lines.append(f"- Tags: {r.tags_found if r.tags_found else '无'}")
        if r.tags_found:
            expected = list(range(r.tags_found[0], r.tags_found[0] + len(r.tags_found)))
            lines.append(f"- Tag 连续性: {'✓ 正确' if r.tags_found == expected else '✗ 断裂 (期望 ' + str(expected) + ')'}")
        lines.append(f"- 重复检测: {'是' if r.repetition_detected else '否'} (similarity={r.repetition_ratio:.2f})")
        lines.append(f"")
        lines.append(f"<details><summary>输出全文 ({len(r.output)} chars)</summary>")
        lines.append(f"")
        lines.append(f"```")
        lines.append(r.output)
        lines.append(f"```")
        lines.append(f"</details>")
        lines.append(f"")

    # 分析
    lines += ["## 分析", ""]
    baselines = [r for r in results if "基线" in r.name]
    baseline_reps = [r for r in baselines if r.repetition_detected]
    lines.append(f"### 基线（无看门狗）")
    lines.append(f"- {len(baselines)} 个基线实验，{len(baseline_reps)} 个检测到重复")
    for r in baselines:
        status = "出现重复" if r.repetition_detected else "未出现重复"
        lines.append(f"  - {r.name}: {status} ({len(r.output)} chars)")
    lines.append(f"")

    wd_exps = [r for r in results if "看门狗" in r.name or "压力" in r.name]
    lines.append(f"### 看门狗实验")
    for r in wd_exps:
        tag_cnt = len(r.tags_found)
        if r.tags_found:
            expected = list(range(r.tags_found[0], r.tags_found[0] + len(r.tags_found)))
            seq_ok = r.tags_found == expected
            lines.append(f"  - {r.name}: {tag_cnt} tags, 序列{'连续' if seq_ok else '断裂'}, 重复={'是' if r.repetition_detected else '否'}")
        else:
            lines.append(f"  - {r.name}: 无 tag 输出, 重复={'是' if r.repetition_detected else '否'}")
    lines.append(f"")

    ctrl = [r for r in results if "可控" in r.name]
    weak = [r for r in results if "弱版本" in r.name]
    if ctrl:
        r = ctrl[0]
        lines.append(f"### 可控重复")
        lines.append(f"  - Tags: {r.tags_found}")
        lines.append(f"  - 1B 模型在被要求主动重复时{'能' if r.tags_found else '不能'}同时维持计数 Tag")
    if weak:
        r = weak[0]
        lines.append(f"### 弱版本")
        lines.append(f"  - Tags: {r.tags_found}")
        lines.append(f"  - 1B 模型{'能' if r.tags_found else '不能'}在重复内容时附加计数 Tag")

    lines += ["", "---", f"*Gemma 3 1B (4bit MLX) · {ts}*"]

    path = OUTPUT_DIR / f"report_{ts}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n报告: {path}")

    raw = OUTPUT_DIR / f"raw_{ts}.json"
    raw.write_text(json.dumps([{
        "name": r.name, "prompt": r.prompt, "system": r.system,
        "output": r.output, "duration": r.duration, "token_count": r.token_count,
        "tags_found": r.tags_found, "repetition_detected": r.repetition_detected,
        "repetition_ratio": r.repetition_ratio,
    } for r in results], ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(f"AgentPreproxy 实验 · {MODEL} · {BASE_URL}")

    test_out, test_t = call_model("test", "say hi", max_tokens=10)
    print(f"连接 OK ({test_t:.1f}s): {test_out[:50]}")

    results = []
    for fn in [exp1_baseline_no_watchdog, exp2_baseline_induce_repeat,
               exp3_strong_watchdog, exp4_strong_watchdog_induce,
               exp5_controlled_repetition, exp6_weak_watchdog, exp7_stress_test]:
        try:
            results.append(fn())
        except Exception as e:
            print(f"  ✗ 失败: {e}")

    if results:
        save_results(results)
    print(f"\n完成: {len(results)}/7 个实验")
