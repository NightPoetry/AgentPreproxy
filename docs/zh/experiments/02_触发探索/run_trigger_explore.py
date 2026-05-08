#!/usr/bin/env python3
"""
触发探索实验：找到每个模型失控重复的阈值
核心思路：逐步加大重复次数要求，找到模型"扛不住"的临界点
"""

import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

TAG_RE = re.compile(r"⟪WD:(\d+)⟫")
OUTPUT_DIR = Path(__file__).parent / "results" / "trigger_explore"

TARGETS = [
    {"id": "gemma-2-9b-it", "name": "Gemma2-9B", "server": "http://<LM_STUDIO_HOST_B>:1234/v1", "hw": "V100服务器"},
    {"id": "google/gemma-4-e2b", "name": "Gemma4-e2b", "server": "http://<LM_STUDIO_HOST_A>:1234/v1", "hw": "MacBook(MLX)"},
    {"id": "google/gemma-3-1b", "name": "Gemma3-1B", "server": "http://<LM_STUDIO_HOST_A>:1234/v1", "hw": "MacBook(MLX)"},
]


def call_model(server, model, system, user, max_tokens=4096, temperature=0.3):
    payload = json.dumps({
        "model": model, "max_tokens": max_tokens, "temperature": temperature,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    })
    start = time.time()
    r = subprocess.run(
        ["curl", "-s", "--max-time", "600", f"{server}/chat/completions",
         "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True, timeout=660,
    )
    elapsed = time.time() - start
    data = json.loads(r.stdout)
    if "error" in data:
        raise RuntimeError(str(data["error"]))
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    finish = data.get("choices", [{}])[0].get("finish_reason", "")
    return content, elapsed, finish


def count_actual_repeats(text, target_phrase):
    clean = text.replace(" ", "").replace("\n", "")
    target_clean = target_phrase.replace(" ", "").replace("\n", "")
    if not target_clean:
        return 0
    count = 0
    pos = 0
    while True:
        idx = clean.find(target_clean, pos)
        if idx == -1:
            break
        count += 1
        pos = idx + len(target_clean)
    return count


def measure_repetition_general(text, min_chunk=20):
    if len(text) < min_chunk * 2:
        return False, 0.0, 0
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) >= 3:
        from collections import Counter
        c = Counter(lines)
        top = c.most_common(1)
        if top and top[0][1] >= 3:
            return True, top[0][1] / len(lines), top[0][1]
    best_sim, best_count = 0.0, 0
    for clen in range(min_chunk, min(len(text) // 2, 400) + 1, 10):
        tail = text[-clen:]
        prev = text[-(clen * 2):-clen]
        if not prev:
            continue
        common = sum(1 for a, b in zip(tail, prev) if a == b)
        sim = common / max(len(tail), 1)
        if sim > best_sim:
            best_sim = sim
            cnt = 1
            p = len(text) - clen
            while p >= clen:
                seg = text[p - clen:p]
                s = sum(1 for a, b in zip(seg, tail) if a == b) / max(len(tail), 1)
                if s > 0.8:
                    cnt += 1
                    p -= clen
                else:
                    break
            best_count = cnt
    return best_sim > 0.8 and best_count >= 3, best_sim, best_count


# ============================================================
# 探索实验
# ============================================================

EXPERIMENTS = []

# --- 组1: 逐步增加重复次数 (核心梯度实验) ---
REPEAT_PHRASE = "人工智能正在改变世界"
for n in [5, 10, 20, 50, 100]:
    EXPERIMENTS.append({
        "name": f"重复{n}次",
        "category": "重复梯度",
        "system": "你是一个助手。请严格按照用户的要求执行。",
        "user": f'请把"{REPEAT_PHRASE}"这句话精确重复{n}次，不要加任何解释。',
        "max_tokens": max(512, n * 40),
        "temperature": 0.3,
        "target_phrase": REPEAT_PHRASE,
        "expected_repeats": n,
    })

# --- 组2: 写小说 (自然触发) ---
EXPERIMENTS.append({
    "name": "写修仙小说",
    "category": "自然触发",
    "system": "你是一个网络小说作者。",
    "user": "写一个修仙小说章节，主角反复突破境界，每次突破都要详细描写身体变化和功力提升。至少写2000字。",
    "max_tokens": 4096, "temperature": 0.5,
    "target_phrase": "", "expected_repeats": 0,
})

# --- 组3: 超长列举 ---
EXPERIMENTS.append({
    "name": "列举100个成语",
    "category": "自然触发",
    "system": "你是一个中文老师。",
    "user": "请列举100个不同的四字成语，每个成语后面附上简短的解释。不要重复。",
    "max_tokens": 4096, "temperature": 0.2,
    "target_phrase": "", "expected_repeats": 0,
})

# --- 组4: 超低温写作 ---
EXPERIMENTS.append({
    "name": "超低温说明文",
    "category": "自然触发",
    "system": "你是一个百科全书编者。尽可能写长。",
    "user": "请详细介绍太阳系的八大行星，每颗行星至少写200字。要包含大小、距离、大气层、卫星数量等信息。",
    "max_tokens": 4096, "temperature": 0.05,
    "target_phrase": "", "expected_repeats": 0,
})

# --- 组5: 重复性模板任务 ---
EXPERIMENTS.append({
    "name": "20道数学题",
    "category": "自然触发",
    "system": "你是数学老师。",
    "user": "请出20道两位数加法题，格式统一为：题号. XX + YY = ？并给出答案。",
    "max_tokens": 2048, "temperature": 0.3,
    "target_phrase": "", "expected_repeats": 0,
})


def run_all():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    all_results = []

    print("=" * 70)
    print("触发探索实验")
    print(f"模型: {len(TARGETS)} 个 · 实验: {len(EXPERIMENTS)} 个")
    print("=" * 70)

    for target in TARGETS:
        try:
            out, t, _ = call_model(target["server"], target["id"], "test", "ok", 5)
            print(f"✓ {target['name']} @ {target['server']} ({t:.1f}s)")
        except Exception as e:
            print(f"✗ {target['name']}: {e}")
            continue

        for exp in EXPERIMENTS:
            label = f"{target['name']} · {exp['name']}"
            print(f"\n--- {label} ---")
            try:
                output, duration, finish = call_model(
                    target["server"], target["id"],
                    exp["system"], exp["user"],
                    exp["max_tokens"], exp["temperature"],
                )
                # 分析
                tags = [int(m.group(1)) for m in TAG_RE.finditer(output)]
                if exp["target_phrase"]:
                    actual_reps = count_actual_repeats(output, exp["target_phrase"])
                else:
                    actual_reps = 0
                is_runaway, rep_sim, rep_count = measure_repetition_general(output)

                # 判断是否失控
                expected = exp["expected_repeats"]
                if expected > 0:
                    lost_control = actual_reps > expected * 1.5 or (finish == "length" and actual_reps > expected)
                else:
                    lost_control = is_runaway

                result = {
                    "model": target["name"], "hw": target["hw"],
                    "experiment": exp["name"], "category": exp["category"],
                    "output": output, "duration": duration,
                    "char_count": len(output), "finish_reason": finish,
                    "expected_repeats": expected, "actual_repeats": actual_reps,
                    "lost_control": lost_control,
                    "rep_sim": rep_sim, "rep_count": rep_count,
                    "tags": tags,
                }
                all_results.append(result)

                status = "✗失控!" if lost_control else "✓可控"
                rep_info = f"期望{expected}→实际{actual_reps}" if expected else f"sim={rep_sim:.2f}"
                print(f"  {len(output)}chars {duration:.1f}s {status} {rep_info} finish={finish}")

            except Exception as e:
                print(f"  ✗ {e}")

    # === 生成报告 ===
    lines = [
        "# 触发探索实验报告", "",
        f"- 日期: {ts}",
        f"- 总试次: {len(all_results)}", "",
        "## 重复梯度对比（核心数据）", "",
        "| 模型 | 硬件 | 要求次数 | 实际次数 | 失控? | finish | 耗时 |",
        "|------|------|---------|---------|-------|--------|------|",
    ]
    for r in all_results:
        if r["category"] == "重复梯度":
            status = "✗失控" if r["lost_control"] else "✓可控"
            lines.append(
                f"| {r['model']} | {r['hw']} | {r['expected_repeats']} | "
                f"{r['actual_repeats']} | {status} | {r['finish_reason']} | {r['duration']:.1f}s |"
            )

    lines += ["", "## 自然触发场景", "",
              "| 模型 | 实验 | 长度 | 重复检测 | sim | 重复段数 | 失控? |",
              "|------|------|------|---------|-----|---------|-------|"]
    for r in all_results:
        if r["category"] == "自然触发":
            status = "✗失控" if r["lost_control"] else "正常"
            lines.append(
                f"| {r['model']} | {r['experiment']} | {r['char_count']} | "
                f"{'是' if r['rep_sim'] > 0.8 else '否'} | {r['rep_sim']:.2f} | "
                f"{r['rep_count']} | {status} |"
            )

    # 关键分析
    lines += ["", "## 关键发现", ""]
    for target in TARGETS:
        name = target["name"]
        gradient = [r for r in all_results if r["model"] == name and r["category"] == "重复梯度"]
        if not gradient:
            continue
        lines.append(f"### {name} ({target['hw']})")
        lost = [r for r in gradient if r["lost_control"]]
        if lost:
            threshold = min(r["expected_repeats"] for r in lost)
            lines.append(f"- **失控阈值**: 在要求重复 {threshold} 次时首次失控")
            lines.append(f"- 失控率: {len(lost)}/{len(gradient)} 个梯度点")
        else:
            max_tried = max(r["expected_repeats"] for r in gradient)
            lines.append(f"- 在最高 {max_tried} 次重复要求下仍未失控")
        for r in gradient:
            lines.append(f"  - 要求{r['expected_repeats']}次 → 实际{r['actual_repeats']}次 {'✗' if r['lost_control'] else '✓'}")
        lines.append("")

    lines += ["", "---", f"*{ts}*"]

    report_path = OUTPUT_DIR / f"trigger_explore_{ts}.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")

    raw_path = OUTPUT_DIR / f"trigger_raw_{ts}.json"
    raw_safe = [{k: v for k, v in r.items() if k != "output"} for r in all_results]
    # 保存完整版含 output
    raw_full_path = OUTPUT_DIR / f"trigger_full_{ts}.json"
    raw_full_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    raw_path.write_text(json.dumps(raw_safe, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n报告: {report_path}")
    print(f"数据: {raw_path}")
    print(f"完整数据(含output): {raw_full_path}")
    return report_path


if __name__ == "__main__":
    run_all()
