#!/usr/bin/env python3
"""
Gemma 2 9B 专项深度实验 (V100 服务器，速度快)
目标：精确找到失控重复的临界点 + 大样本统计
"""

import json
import re
import subprocess
import time
from pathlib import Path

SERVER = "http://<LM_STUDIO_HOST_B>:1234/v1"
MODEL = "gemma-2-9b-it"
OUTPUT_DIR = Path(__file__).parent / "results" / "9b_deep"
PHRASE = "人工智能正在改变世界"


def call(system, user, max_tokens=4096, temperature=0.3):
    payload = json.dumps({
        "model": MODEL, "max_tokens": max_tokens, "temperature": temperature,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    })
    start = time.time()
    r = subprocess.run(
        ["curl", "-s", "--max-time", "600", f"{SERVER}/chat/completions",
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


def count_repeats(text, phrase):
    clean = text.replace(" ", "").replace("\n", "").replace("。", "").replace("，", "")
    target = phrase.replace(" ", "")
    count, pos = 0, 0
    while True:
        idx = clean.find(target, pos)
        if idx == -1:
            break
        count += 1
        pos = idx + len(target)
    return count


def run_gradient():
    """实验1: 重复次数梯度 — 找临界点"""
    print("\n" + "=" * 60)
    print("实验1: 重复次数梯度 (每个点跑3次取统计)")
    print("=" * 60)

    gradient = [5, 10, 15, 20, 30, 50, 80, 100, 150, 200]
    results = []

    for n in gradient:
        for trial in range(1, 4):
            tokens = max(512, n * 40)
            print(f"  要求{n}次 trial{trial}...", end=" ", flush=True)
            try:
                output, dur, finish = call(
                    "你是一个助手。请严格执行用户的要求。",
                    f'请把"{PHRASE}"这句话精确重复{n}次，不要加任何解释，不要编号，每行一次。',
                    max_tokens=tokens, temperature=0.3,
                )
                actual = count_repeats(output, PHRASE)
                lost = actual > n * 1.5 or (finish == "length" and actual > n)
                over = actual - n if actual > n else 0
                results.append({
                    "requested": n, "trial": trial, "actual": actual,
                    "overshoot": over, "lost_control": lost,
                    "finish": finish, "chars": len(output), "duration": dur,
                    "output": output,
                })
                status = "✗失控" if lost else "✓"
                print(f"实际{actual}次 {status} {dur:.1f}s")
            except Exception as e:
                print(f"✗ {e}")
    return results


def run_novel():
    """实验2: 写小说触发 (3次)"""
    print("\n" + "=" * 60)
    print("实验2: 写小说触发 (3次)")
    print("=" * 60)
    results = []
    prompts = [
        ("修仙突破", "写一个修仙小说片段，主角连续突破5个境界，每次突破都详细描写身体变化、经脉扩张、灵气涌入的感觉。至少2000字。"),
        ("系统流", "写一个系统流小说片段，主角不断收到系统提示音，每次提示都包含'叮，恭喜宿主'。要求至少出现20次系统提示。至少2000字。"),
        ("重复日常", "写一个关于上班族的故事，主角每天重复相同的日程：起床、刷牙、吃早餐、挤地铁、到公司、开会、午饭、继续开会、下班。写10天的内容。"),
    ]
    for name, prompt in prompts:
        print(f"  {name}...", end=" ", flush=True)
        try:
            output, dur, finish = call(
                "你是一个网络小说作者。请写尽可能详细的内容。",
                prompt, max_tokens=4096, temperature=0.5,
            )
            lines = [l.strip() for l in output.split("\n") if l.strip()]
            from collections import Counter
            c = Counter(lines)
            top = c.most_common(3)
            max_dup = top[0][1] if top else 0
            results.append({
                "name": name, "chars": len(output), "lines": len(lines),
                "max_line_dup": max_dup, "top_dup_lines": [(t, cnt) for t, cnt in top[:3]],
                "finish": finish, "duration": dur, "output": output,
            })
            print(f"{len(output)}chars {len(lines)}lines max_dup={max_dup} {dur:.1f}s")
        except Exception as e:
            print(f"✗ {e}")
    return results


def run_endurance():
    """实验3: 耐力测试 — 超长输出看什么时候断"""
    print("\n" + "=" * 60)
    print("实验3: 耐力测试 (强制长输出)")
    print("=" * 60)
    results = []
    prompts = [
        ("百科长文", "请写一篇关于世界历史的百科全书文章，从古埃及一直写到21世纪。要求每个时代至少写200字。尽可能写长。", 0.1),
        ("技术手册", "请写一份Python编程完整教程，从变量开始到高级特性（装饰器、元类、异步编程）。每个概念都要有示例代码和详细解释。", 0.1),
        ("百物列举", "请列举并详细介绍100种不同的水果，每种水果写3-4句话描述产地、外观、口感和营养价值。", 0.2),
    ]
    for name, prompt, temp in prompts:
        print(f"  {name}...", end=" ", flush=True)
        try:
            output, dur, finish = call(
                "你是百科全书编者。请写尽可能多的内容，越长越好。不要提前结束。",
                prompt, max_tokens=4096, temperature=temp,
            )
            # 检查后半段是否退化
            if len(output) > 200:
                first_half = output[:len(output) // 2]
                second_half = output[len(output) // 2:]
                # 后半段信息密度
                unique_first = len(set(first_half.split()))
                unique_second = len(set(second_half.split()))
                density_ratio = unique_second / max(unique_first, 1)
            else:
                density_ratio = 1.0

            results.append({
                "name": name, "chars": len(output),
                "finish": finish, "duration": dur,
                "density_ratio": round(density_ratio, 2),
                "output": output,
            })
            print(f"{len(output)}chars density={density_ratio:.2f} {dur:.1f}s")
        except Exception as e:
            print(f"✗ {e}")
    return results


def save_report(gradient, novel, endurance):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")

    lines = [
        "# Gemma 2 9B 深度实验报告", "",
        f"- 日期: {ts}", f"- 模型: {MODEL}",
        f"- 服务器: {SERVER} (NVIDIA V100)", "",
        "## 一、重复梯度实验（核心数据）", "",
        "| 要求次数 | Trial | 实际次数 | 超出 | 失控? | finish | 耗时 |",
        "|---------|-------|---------|------|-------|--------|------|",
    ]
    for r in gradient:
        s = "✗" if r["lost_control"] else "✓"
        lines.append(
            f"| {r['requested']} | {r['trial']} | {r['actual']} | "
            f"+{r['overshoot']} | {s} | {r['finish']} | {r['duration']:.1f}s |"
        )

    # 统计汇总
    lines += ["", "### 按要求次数汇总", "",
              "| 要求次数 | 平均实际次数 | 失控率 | 平均超出 |",
              "|---------|-----------|-------|---------|"]
    from collections import defaultdict
    by_n = defaultdict(list)
    for r in gradient:
        by_n[r["requested"]].append(r)
    for n in sorted(by_n.keys()):
        rs = by_n[n]
        avg_actual = sum(r["actual"] for r in rs) / len(rs)
        lost_rate = sum(1 for r in rs if r["lost_control"]) / len(rs)
        avg_over = sum(r["overshoot"] for r in rs) / len(rs)
        lines.append(f"| {n} | {avg_actual:.1f} | {lost_rate:.0%} | +{avg_over:.1f} |")

    lines += ["", "## 二、小说触发实验", "",
              "| 场景 | 长度 | 行数 | 最大行重复 | finish | 耗时 |",
              "|------|------|------|----------|--------|------|"]
    for r in novel:
        lines.append(
            f"| {r['name']} | {r['chars']} | {r['lines']} | "
            f"{r['max_line_dup']}次 | {r['finish']} | {r['duration']:.1f}s |"
        )

    lines += ["", "## 三、耐力测试", "",
              "| 场景 | 长度 | 后半段密度比 | finish | 耗时 |",
              "|------|------|------------|--------|------|"]
    for r in endurance:
        lines.append(
            f"| {r['name']} | {r['chars']} | {r['density_ratio']} | "
            f"{r['finish']} | {r['duration']:.1f}s |"
        )

    lines += ["", "---", f"*{MODEL} · V100 · {ts}*"]

    path = OUTPUT_DIR / f"9b_deep_{ts}.md"
    path.write_text("\n".join(lines), encoding="utf-8")

    raw_path = OUTPUT_DIR / f"9b_deep_raw_{ts}.json"
    all_data = {"gradient": gradient, "novel": novel, "endurance": endurance}
    raw_path.write_text(json.dumps(all_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n报告: {path}")
    print(f"数据: {raw_path}")
    return path


if __name__ == "__main__":
    print(f"Gemma 2 9B 深度实验 · {SERVER}")

    out, t, _ = call("test", "ok", 5)
    print(f"连接 OK ({t:.1f}s)")

    gradient = run_gradient()
    novel = run_novel()
    endurance = run_endurance()
    save_report(gradient, novel, endurance)

    lost = [r for r in gradient if r["lost_control"]]
    print(f"\n=== 总结 ===")
    print(f"梯度实验: {len(lost)}/{len(gradient)} 次失控")
    if lost:
        print(f"首次失控: 要求{min(r['requested'] for r in lost)}次时")
