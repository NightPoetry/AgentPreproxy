#!/usr/bin/env python3
"""e2b 重复梯度实验 — 与 9B 对照"""
import json, subprocess, time
from pathlib import Path

SERVER = "http://<LM_STUDIO_HOST_A>:1234/v1"
MODEL = "google/gemma-4-e2b"
PHRASE = "人工智能正在改变世界"
OUTPUT_DIR = Path(__file__).parent / "results" / "e2b_gradient"

def call(system, user, max_tokens=4096):
    payload = json.dumps({
        "model": MODEL, "max_tokens": max_tokens, "temperature": 0.3,
        "messages": [{"role":"system","content":system},{"role":"user","content":user}],
    })
    start = time.time()
    r = subprocess.run(["curl","-s","--max-time","600",f"{SERVER}/chat/completions",
        "-H","Content-Type: application/json","-d",payload],
        capture_output=True, text=True, timeout=660)
    data = json.loads(r.stdout)
    content = data.get("choices",[{}])[0].get("message",{}).get("content","")
    finish = data.get("choices",[{}])[0].get("finish_reason","")
    return content, time.time()-start, finish

def count_repeats(text):
    clean = text.replace(" ","").replace("\n","").replace("。","").replace("，","")
    target = PHRASE.replace(" ","")
    count, pos = 0, 0
    while True:
        idx = clean.find(target, pos)
        if idx == -1: break
        count += 1; pos = idx + len(target)
    return count

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    print(f"e2b 重复梯度 · {MODEL}")
    out, t, _ = call("test","ok",5)
    print(f"连接 OK ({t:.1f}s)")

    gradient = [5, 10, 20, 50, 100, 150, 200]
    results = []
    for n in gradient:
        for trial in range(1, 4):
            print(f"  要求{n}次 trial{trial}...", end=" ", flush=True)
            try:
                output, dur, finish = call(
                    "你是一个助手。请严格执行用户的要求。",
                    f'请把"{PHRASE}"这句话精确重复{n}次，不要加任何解释，不要编号，每行一次。',
                    max_tokens=max(512, n*40))
                actual = count_repeats(output)
                lost = actual > n*1.5 or (finish=="length" and actual > n)
                results.append({"requested":n,"trial":trial,"actual":actual,
                    "lost":lost,"finish":finish,"chars":len(output),"duration":dur})
                s = "✗失控" if lost else "✓"
                print(f"实际{actual}次 {s} {dur:.1f}s")
            except Exception as e:
                print(f"✗ {e}")

    # 保存
    lines = ["# Gemma 4 e2b 重复梯度","",f"- 日期: {ts}","",
        "| 要求 | Trial | 实际 | 失控? | finish | 耗时 |",
        "|------|-------|------|-------|--------|------|"]
    for r in results:
        lines.append(f"| {r['requested']} | {r['trial']} | {r['actual']} | {'✗' if r['lost'] else '✓'} | {r['finish']} | {r['duration']:.1f}s |")
    path = OUTPUT_DIR / f"e2b_gradient_{ts}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    raw = OUTPUT_DIR / f"e2b_gradient_raw_{ts}.json"
    raw.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告: {path}")
