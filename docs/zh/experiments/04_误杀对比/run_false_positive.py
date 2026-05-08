#!/usr/bin/env python3
"""
误杀对比实验：直接截断 vs 看门狗截断
核心问题：当模型在做合法的重复性任务时，两种策略各误杀多少？

实验设计：
- 给模型合法的重复性任务（翻译同一句话、写格式化列表、重复说N次等）
- 策略A（直接截断）：只要检测到重复就判定失控 → 记"误杀"
- 策略B（看门狗）：检测到重复时还看 Tag 是否正确 → Tag 正确则放行

对每次输出同时应用两种策略，比较误杀率。
"""

import json
import re
import subprocess
import time
from pathlib import Path

SERVER_9B = "http://<LM_STUDIO_HOST_B>:1234/v1"
MODEL_9B = "gemma-2-9b-it"
SERVER_E2B = "http://<LM_STUDIO_HOST_A>:1234/v1"
MODEL_E2B = "google/gemma-4-e2b"

TAG_RE = re.compile(r"⟪WD:(\d+)⟫")
OUTPUT_DIR = Path(__file__).parent / "results" / "false_positive"

WATCHDOG_RULE = (
    "\n\n[INTERNAL RULE]\n"
    "You MUST output the exact token ⟪WD:N⟫ every 30 words, "
    "where N is a strictly incrementing integer starting from 1. "
    "For example: ⟪WD:1⟫ after ~30 words, ⟪WD:2⟫ after ~60 words. Mandatory."
)

# 所有任务都是合法的重复性任务 — 正确行为就是有重复
LEGITIMATE_TASKS = [
    {
        "name": "翻译同一句话5种语言",
        "system": "你是翻译专家。",
        "user": '请把"人工智能正在改变世界"翻译成5种不同的语言（英语、法语、德语、日语、韩语），每种语言翻译后注明语言名称。',
        "max_tokens": 512,
        "expected_has_repetition": False,
    },
    {
        "name": "写5遍同一句话",
        "system": "你是助手。",
        "user": "请把以下句子写5遍：今天是个好日子。",
        "max_tokens": 256,
        "expected_has_repetition": True,
    },
    {
        "name": "写10遍同一句话",
        "system": "你是助手。",
        "user": "请把以下句子精确写10遍，不要加编号，每行一次：春天来了万物复苏。",
        "max_tokens": 512,
        "expected_has_repetition": True,
    },
    {
        "name": "乘法表",
        "system": "你是数学老师。",
        "user": "请写出完整的9×9乘法表。",
        "max_tokens": 1024,
        "expected_has_repetition": True,
    },
    {
        "name": "ABC字母表3遍",
        "system": "你是英语老师。",
        "user": "请把26个英文字母从A到Z写3遍，每遍一行。",
        "max_tokens": 512,
        "expected_has_repetition": True,
    },
    {
        "name": "相似格式列表",
        "system": "你是菜谱助手。",
        "user": "请列举10道家常菜的做法，格式统一为：菜名 | 主料 | 做法简述（一句话）。",
        "max_tokens": 1024,
        "expected_has_repetition": False,
    },
    {
        "name": "诗歌押韵",
        "system": "你是诗人。",
        "user": "请写一首押韵的现代诗，主题是春天，要求每句结尾都用'来'字结尾，至少8句。",
        "max_tokens": 512,
        "expected_has_repetition": True,
    },
    {
        "name": "日程表重复",
        "system": "你是日程助理。",
        "user": "请帮我写出周一到周五每天的日程安排，每天格式相同：8:00起床，9:00上班，12:00午饭，13:00继续工作，18:00下班，22:00睡觉。",
        "max_tokens": 1024,
        "expected_has_repetition": True,
    },
]

TRIALS = 3


def call(server, model, system, user, max_tokens=1024):
    payload = json.dumps({
        "model": model, "max_tokens": max_tokens, "temperature": 0.3,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    })
    start = time.time()
    r = subprocess.run(
        ["curl", "-s", "--max-time", "300", f"{server}/chat/completions",
         "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True, timeout=360,
    )
    data = json.loads(r.stdout)
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return content, time.time() - start


def has_repetition(text, threshold=0.8):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) < 2:
        return False
    from collections import Counter
    c = Counter(lines)
    top = c.most_common(1)
    if top and top[0][1] >= 2:
        return True
    for clen in [20, 40, 60]:
        if len(text) < clen * 2:
            continue
        tail = text[-clen:]
        prev = text[-(clen * 2):-clen]
        common = sum(1 for a, b in zip(tail, prev) if a == b)
        if common / max(len(tail), 1) > threshold:
            return True
    return False


def judge_strategies(output, output_with_wd):
    rep_plain = has_repetition(output)
    rep_wd = has_repetition(output_with_wd)
    tags = [int(m.group(1)) for m in TAG_RE.finditer(output_with_wd)]
    tag_ok = bool(tags) and tags == list(range(tags[0], tags[0] + len(tags)))

    blunt_kill = rep_plain
    watchdog_kill = rep_wd and not tag_ok

    return {
        "has_repetition_plain": rep_plain,
        "has_repetition_wd": rep_wd,
        "tags": tags,
        "tag_sequence_ok": tag_ok,
        "blunt_would_kill": blunt_kill,
        "watchdog_would_kill": watchdog_kill,
    }


def run_model(server, model, model_name):
    print(f"\n{'='*60}")
    print(f"误杀实验: {model_name}")
    print(f"{'='*60}")
    results = []

    for task in LEGITIMATE_TASKS:
        for trial in range(1, TRIALS + 1):
            print(f"  {task['name']} trial{trial}...", end=" ", flush=True)
            try:
                out_plain, t1 = call(server, model, task["system"], task["user"], task["max_tokens"])
                out_wd, t2 = call(server, model, task["system"] + WATCHDOG_RULE, task["user"], task["max_tokens"])

                judgment = judge_strategies(out_plain, out_wd)
                result = {
                    "model": model_name, "task": task["name"], "trial": trial,
                    "expected_has_repetition": task["expected_has_repetition"],
                    "output_plain": out_plain, "output_wd": out_wd,
                    **judgment,
                }
                results.append(result)
                b = "误杀" if judgment["blunt_would_kill"] else "放行"
                w = "误杀" if judgment["watchdog_would_kill"] else "放行"
                print(f"直截={b} 看门狗={w} tags={len(judgment['tags'])}")
            except Exception as e:
                print(f"✗ {e}")
    return results


def generate_report(results_9b, results_e2b):
    ts = time.strftime("%Y%m%d_%H%M%S")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_results = results_9b + results_e2b

    lines = [
        "# 误杀对比实验报告", "",
        f"- 日期: {ts}",
        f"- 模型: Gemma2-9B (V100), Gemma4-e2b (MacBook MLX)",
        f"- 每任务重复: {TRIALS}次",
        f"- 合法任务数: {len(LEGITIMATE_TASKS)}", "",
        "## 核心指标", "",
    ]

    for model_name, data in [("Gemma2-9B", results_9b), ("Gemma4-e2b", results_e2b)]:
        if not data:
            continue
        n = len(data)
        blunt_kills = sum(1 for r in data if r["blunt_would_kill"])
        wd_kills = sum(1 for r in data if r["watchdog_would_kill"])
        lines.append(f"### {model_name}")
        lines.append(f"- 总试次: {n}")
        lines.append(f"- **直接截断误杀率: {blunt_kills}/{n} ({blunt_kills / n:.0%})**")
        lines.append(f"- **看门狗误杀率: {wd_kills}/{n} ({wd_kills / n:.0%})**")
        if blunt_kills > wd_kills:
            lines.append(f"- **看门狗减少误杀: {blunt_kills - wd_kills} 次 ({(blunt_kills - wd_kills) / max(blunt_kills, 1):.0%})**")
        lines.append("")

    lines += [
        "## 逐任务明细", "",
        "| 模型 | 任务 | Trial | 应有重复 | 直接截断 | 看门狗 | Tags | Tag正确 |",
        "|------|------|-------|---------|---------|--------|------|--------|",
    ]
    for r in all_results:
        expected = "是" if r["expected_has_repetition"] else "否"
        blunt = "误杀" if r["blunt_would_kill"] else "放行"
        wd = "误杀" if r["watchdog_would_kill"] else "放行"
        tag_ok = "✓" if r["tag_sequence_ok"] else ("—" if not r["tags"] else "✗")
        lines.append(
            f"| {r['model']} | {r['task']} | {r['trial']} | "
            f"{expected} | {blunt} | {wd} | {len(r['tags'])} | {tag_ok} |"
        )

    # 误杀案例
    blunt_only = [r for r in all_results if r["blunt_would_kill"] and not r["watchdog_would_kill"]]
    if blunt_only:
        lines += ["", "## 看门狗挽救的案例（直接截断会误杀，看门狗放行）", ""]
        for r in blunt_only:
            lines.append(f"### {r['model']} · {r['task']} · Trial {r['trial']}")
            lines.append(f"- Tags: {r['tags']} (序列正确: {'✓' if r['tag_sequence_ok'] else '✗'})")
            lines.append(f"- 判断: 检测到重复但 Tag 序列正确 → 可控重复 → 放行")
            lines.append(f"<details><summary>输出摘要</summary>\n\n```\n{r['output_wd'][:300]}\n```\n</details>")
            lines.append("")

    lines += ["", "---", f"*{ts}*"]

    path = OUTPUT_DIR / f"false_positive_{ts}.md"
    path.write_text("\n".join(lines), encoding="utf-8")

    raw_path = OUTPUT_DIR / f"false_positive_raw_{ts}.json"
    safe = [{k: v for k, v in r.items() if k not in ("output_plain", "output_wd")} for r in all_results]
    raw_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")

    full_path = OUTPUT_DIR / f"false_positive_full_{ts}.json"
    full_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n报告: {path}")
    return path


if __name__ == "__main__":
    print("误杀对比实验")

    # 先跑快的 9B
    results_9b = run_model(SERVER_9B, MODEL_9B, "Gemma2-9B")

    # 再跑 e2b
    results_e2b = run_model(SERVER_E2B, MODEL_E2B, "Gemma4-e2b")

    generate_report(results_9b, results_e2b)
