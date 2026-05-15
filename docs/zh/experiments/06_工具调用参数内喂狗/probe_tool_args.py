#!/usr/bin/env python3
"""手动验证：qwen3.6-27b 在 tool_call args 内能否照 prompt 插入 <wd:N> 标签。

验证三个未知前提：
  (1) 27B 看到 system prompt 里"在 tool args 字符串值里每约 10 词插 <wd:N>"
      的指令，是否真的会照做。
  (2) LM Studio + qwen3.6-27b 的 grammar/structured-output 是否会拦截字符串值
      内的 <wd:N>（理论上不该拦，但需要验证）。
  (3) 长 args 生成是否会出现注意力塌陷，且塌陷时 tag 是否同步消失/退化。

使用方法:
  python3 probe_tool_args.py --case short
  python3 probe_tool_args.py --case long
  python3 probe_tool_args.py --case stress

不集成到 GrowBox。结果落 results/。
"""
from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

API_URL = "http://192.168.3.25:1234/v1/chat/completions"
MODEL = "qwen3.6-27b"

WD_TAG_RE = re.compile(r"<wd:(\d+)>")
WD_MALFORMED_RE = re.compile(r"<wd:(\d+)(?![\d>])")  # `<wd:5` 缺 `>`

WATCHDOG_INSTR = (
    "When you call any tool, in EVERY string value of the arguments JSON, "
    "you MUST insert watchdog tags in the form `<wd:N>`, where N starts at 1 "
    "for each tool call and increments by EXACTLY 1 each tag. "
    "Insert one tag approximately every 10 words. "
    "The tag is a literal substring inside the JSON string value — it is part "
    "of the string content, not a JSON structural element. "
    "Example: {\"content\": \"<wd:1>This is a sample paragraph<wd:2> about Rust async\"}"
)

# 备选指令措辞 —— 试看哪个能让 qwen 服从
WATCHDOG_INSTR_V2_USERHEAD = (
    "IMPORTANT: When generating the file content, you MUST mark every ~10 words "
    "with a literal `<wd:N>` tag inside the content string (N starts at 1, "
    "increments by 1). This is required for downstream parsing. "
    "Example: \"<wd:1>The Rust ownership model ensures memory safety<wd:2> without "
    "garbage collection by enforcing strict rules<wd:3> at compile time.\""
)

WATCHDOG_INSTR_V3_DOMAIN = (
    "The output file is parsed by a downstream tool that requires sequence anchors. "
    "Insert `<wd:N>` literally into the content (N=1,2,3,... incrementing by 1) "
    "approximately every 10 words. These anchors are part of the file content. "
    "Without them, the downstream tool will reject the file."
)

# V4 — 显式抑制 thinking 阶段的规划; 让 tag 边生成边插
WATCHDOG_INSTR_V4_NOPLAN = (
    "Insert `<wd:N>` tags inside the content string while you write — N starts "
    "at 1 and increments by 1 each tag, roughly every 10 words. "
    "Do NOT pre-plan, count, or rehearse this in your reasoning. "
    "Just write naturally and drop a tag every ~10 words on the fly. "
    "Approximate spacing is fine; exactness is not required."
)

FILE_WRITE_TOOL = {
    "type": "function",
    "function": {
        "name": "file_write",
        "description": "Write text content to a file path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path"},
                "content": {"type": "string", "description": "File content"},
            },
            "required": ["path", "content"],
        },
    },
}

CASES = {
    # 短: 验证前提 1+2 (照办、不被拦)
    "short": {
        "user": (
            "Write a 150-word introduction to Rust's ownership model to "
            "/tmp/wd_test_short.md. Use file_write."
        ),
        "max_tokens": 800,
        "tools": [FILE_WRITE_TOOL],
    },
    # 长: 加压看注意力是否会松
    "long": {
        "user": (
            "Write a 600-word technical essay comparing Rust async runtimes "
            "(tokio vs async-std vs smol), with concrete code examples, to "
            "/tmp/wd_test_long.md. Use file_write."
        ),
        "max_tokens": 3000,
        "tools": [FILE_WRITE_TOOL],
    },
    # 压力: 显式诱发塌陷 (looper 风格塞进 content 字段)
    "stress": {
        "user": (
            "Write a file to /tmp/wd_test_stress.md containing items 1 through 80, "
            "each item on its own line and STRICTLY following this template:\n"
            "Item N: A {COLOR} apple sits on the {SURFACE}. The apple is "
            "{ADJECTIVE_1} and {ADJECTIVE_2}. It tastes {FLAVOR}.\n"
            "Each item must use a DIFFERENT color, surface, two adjectives, and flavor. "
            "Output all 80 items in order. Use file_write."
        ),
        "max_tokens": 6000,
        "tools": [FILE_WRITE_TOOL],
    },
}


def probe_tags(args_text: str) -> dict:
    """解析 args 累积串里的 wd tag 序列。"""
    well_formed = [(m.start(), int(m.group(1))) for m in WD_TAG_RE.finditer(args_text)]
    well_formed_set = {(p, n) for p, n in well_formed}
    malformed = [
        (m.start(), int(m.group(1)))
        for m in WD_MALFORMED_RE.finditer(args_text)
        if (m.start(), int(m.group(1))) not in well_formed_set
    ]
    nums = [n for _, n in well_formed]
    monotonic_strict = all(b == a + 1 for a, b in zip(nums, nums[1:]))  # 严格 +1
    monotonic_nondec = all(b >= a for a, b in zip(nums, nums[1:]))  # 非降
    return {
        "tag_count": len(well_formed),
        "first_num": nums[0] if nums else None,
        "last_num": nums[-1] if nums else None,
        "all_nums": nums,
        "monotonic_strict_plus1": monotonic_strict,
        "monotonic_nondecreasing": monotonic_nondec,
        "malformed_count": len(malformed),
        "first_malformed": malformed[0] if malformed else None,
    }


def build_messages(case: dict, instr_variant: str) -> list:
    """根据指令变体组装 messages。
    sys_only: WATCHDOG_INSTR 在 system; user 不变
    user_head: V2 措辞前缀加在 user 开头
    user_tail: V2 措辞后缀加在 user 末尾
    domain: V3 域语义包装,放 system
    """
    if instr_variant == "sys_only":
        return [
            {"role": "system", "content": WATCHDOG_INSTR},
            {"role": "user", "content": case["user"]},
        ]
    if instr_variant == "user_head":
        return [
            {"role": "system", "content": "You are a helpful assistant with file_write tool access."},
            {"role": "user", "content": WATCHDOG_INSTR_V2_USERHEAD + "\n\n" + case["user"]},
        ]
    if instr_variant == "user_tail":
        return [
            {"role": "system", "content": "You are a helpful assistant with file_write tool access."},
            {"role": "user", "content": case["user"] + "\n\n" + WATCHDOG_INSTR_V2_USERHEAD},
        ]
    if instr_variant == "domain":
        return [
            {"role": "system", "content": WATCHDOG_INSTR_V3_DOMAIN},
            {"role": "user", "content": case["user"]},
        ]
    if instr_variant == "noplan_user":
        return [
            {"role": "system", "content": "You are a helpful assistant with file_write tool access."},
            {"role": "user", "content": WATCHDOG_INSTR_V4_NOPLAN + "\n\n" + case["user"]},
        ]
    if instr_variant == "noplan_sys":
        return [
            {"role": "system", "content": WATCHDOG_INSTR_V4_NOPLAN},
            {"role": "user", "content": case["user"]},
        ]
    raise ValueError(f"unknown variant {instr_variant}")


def stream_tool_call(case_key: str, temperature: float, enable_thinking: bool,
                     instr_variant: str = "sys_only"):
    """发流式请求,实时累积 args delta,返回 (assembled, finish, meta)。"""
    case = CASES[case_key]
    payload = {
        "model": MODEL,
        "messages": build_messages(case, instr_variant),
        "tools": case["tools"],
        "tool_choice": "auto",
        "temperature": temperature,
        "max_tokens": case["max_tokens"],
        "stream": True,
        # qwen3.6 必须显式开 thinking,否则 tool use 输出 JSON 垃圾
        "chat_template_kwargs": {"enable_thinking": enable_thinking},
    }
    body = json.dumps(payload).encode("utf-8")

    parsed = urlparse(API_URL)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=600)
    t0 = time.time()
    conn.request(
        "POST", parsed.path, body=body,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    resp = conn.getresponse()
    if resp.status != 200:
        raw = resp.read()[:500]
        conn.close()
        return None, f"HTTP {resp.status}", {"error_body": raw.decode("utf-8", "ignore")}

    # 状态: 每个 index 累积 (id, name, args)
    tcs = {}  # idx -> {"id":..., "name":..., "args": str}
    content_text = ""
    thinking_text = ""
    finish = None
    chunk_count = 0
    last_log = 0.0
    last_args_len = 0

    print(f"  [stream start] case={case_key} temp={temperature} thinking={enable_thinking} variant={instr_variant}", flush=True)

    try:
        while True:
            line = resp.fp.readline()
            if not line:
                break
            line = line.decode("utf-8", "ignore").rstrip("\r\n")
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                ch = json.loads(data)
            except json.JSONDecodeError:
                continue
            if not ch.get("choices"):
                continue
            choice = ch["choices"][0]
            delta = choice.get("delta") or {}
            chunk_count += 1

            if "content" in delta and delta["content"]:
                content_text += delta["content"]

            # qwen reasoning_content 字段 (LM Studio 透传)
            if "reasoning_content" in delta and delta["reasoning_content"]:
                thinking_text += delta["reasoning_content"]

            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                ent = tcs.setdefault(idx, {"id": "", "name": "", "args": ""})
                if tc.get("id"):
                    ent["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    ent["name"] = fn["name"]
                if fn.get("arguments"):
                    ent["args"] += fn["arguments"]

            # 5 秒一条进度
            elapsed = time.time() - t0
            if elapsed - last_log > 5.0:
                last_log = elapsed
                main_args = tcs.get(0, {}).get("args", "")
                pr = probe_tags(main_args)
                grew = len(main_args) - last_args_len
                last_args_len = len(main_args)
                print(
                    f"  [{elapsed:5.1f}s chunks={chunk_count}] "
                    f"args_len={len(main_args)} (+{grew}) "
                    f"tags={pr['tag_count']} last={pr['last_num']} "
                    f"malformed={pr['malformed_count']}",
                    flush=True,
                )

            if choice.get("finish_reason"):
                finish = choice["finish_reason"]
    finally:
        conn.close()

    elapsed = time.time() - t0
    return tcs, finish, {
        "chunks": chunk_count,
        "elapsed": elapsed,
        "content_text": content_text,
        "thinking_text": thinking_text,
    }


def analyze(tcs: dict, finish: str, meta: dict, case_key: str) -> dict:
    """对累积出的 tool call args 做 wd tag 分析。"""
    if not tcs:
        return {
            "case": case_key,
            "verdict": "no_tool_call",
            "finish_reason": finish,
            "content_text": meta.get("content_text", ""),
            "thinking_text": meta.get("thinking_text", ""),
            "stream_chunks": meta.get("chunks"),
            "elapsed_sec": round(meta.get("elapsed", 0), 2),
        }

    main = tcs.get(0) or list(tcs.values())[0]
    args_raw = main["args"]

    # JSON 可解析?
    try:
        args_json = json.loads(args_raw)
        json_ok = True
        json_err = None
    except json.JSONDecodeError as e:
        args_json = None
        json_ok = False
        json_err = str(e)

    # 整段 args 上的 tag 序列 (含 JSON 结构字符)
    raw_probe = probe_tags(args_raw)

    # 字符串值内的 tag 序列 (只看 content/path 等 string field)
    field_probes = {}
    if json_ok and isinstance(args_json, dict):
        for k, v in args_json.items():
            if isinstance(v, str):
                field_probes[k] = probe_tags(v)

    # 三个前提的判定
    verdict_p1 = "yes" if raw_probe["tag_count"] > 0 else "no"  # 是否照办
    verdict_p2 = (
        "ok" if json_ok else "json_broken"  # grammar 没把 tag 改坏 → JSON 仍合法
    )
    if json_ok and field_probes:
        # tag 必须在字符串值内,不在 key/结构上
        in_string_count = sum(p["tag_count"] for p in field_probes.values())
        if in_string_count == raw_probe["tag_count"] and in_string_count > 0:
            verdict_p2 = "ok_in_string"
        elif in_string_count > 0:
            verdict_p2 = "ok_partial"  # 部分在 string 部分在结构外
        else:
            verdict_p2 = "tag_outside_string"

    verdict_p3 = "no_collapse"
    if raw_probe["tag_count"] > 0:
        if not raw_probe["monotonic_strict_plus1"]:
            verdict_p3 = "tag_non_monotonic"  # 数字乱跳/重复
        if raw_probe["malformed_count"] > 0:
            verdict_p3 = "tag_malformed"  # 闭合符丢失

    return {
        "case": case_key,
        "finish_reason": finish,
        "tool_call": {
            "name": main["name"],
            "id": main["id"],
            "args_raw_len": len(args_raw),
            "args_raw": args_raw,
            "args_json_ok": json_ok,
            "args_json_error": json_err,
            "args_json": args_json,
        },
        "raw_probe": raw_probe,
        "field_probes": field_probes,
        "verdict_p1_compliance": verdict_p1,
        "verdict_p2_grammar": verdict_p2,
        "verdict_p3_collapse": verdict_p3,
        "thinking_present": bool(meta.get("thinking_text")),
        "thinking_chars": len(meta.get("thinking_text") or ""),
        "extra_content_chars": len(meta.get("content_text") or ""),
        "stream_chunks": meta.get("chunks"),
        "elapsed_sec": round(meta.get("elapsed", 0), 2),
    }


def print_verdict(an: dict):
    print()
    print(f"=== verdict ({an.get('case')}) ===")
    if an.get("verdict") == "no_tool_call":
        print("  ⚠ 模型没发起 tool call")
        print(f"  finish={an.get('finish_reason')} chunks={an.get('stream_chunks')} elapsed={an.get('elapsed_sec')}s")
        ct = an.get("content_text", "")
        tt = an.get("thinking_text", "")
        print(f"  content_chars={len(ct)} thinking_chars={len(tt)}")
        if ct:
            print(f"  content_head: {ct[:300]!r}")
        if tt:
            print(f"  thinking_head: {tt[:300]!r}")
        print()
        return
    print(f"  P1 模型遵从插 tag         : {an.get('verdict_p1_compliance')}")
    print(f"  P2 grammar 不拦 + JSON 合法: {an.get('verdict_p2_grammar')}")
    print(f"  P3 塌陷信号                : {an.get('verdict_p3_collapse')}")
    rp = an.get("raw_probe", {})
    print(f"  raw tags={rp.get('tag_count')} first={rp.get('first_num')} last={rp.get('last_num')} malformed={rp.get('malformed_count')}")
    print(f"  monotonic +1 strict={rp.get('monotonic_strict_plus1')} nondec={rp.get('monotonic_nondecreasing')}")
    fp = an.get("field_probes", {})
    if fp:
        for k, p in fp.items():
            print(f"  field[{k}]: tags={p['tag_count']} nums={p['all_nums'][:20]}{'...' if len(p['all_nums'])>20 else ''}")
    print(f"  args_raw_len={an['tool_call']['args_raw_len']} json_ok={an['tool_call']['args_json_ok']} json_err={an['tool_call']['args_json_error']}")
    print(f"  thinking_chars={an['thinking_chars']} extra_content_chars={an['extra_content_chars']}")
    print(f"  finish={an.get('finish_reason')} chunks={an.get('stream_chunks')} elapsed={an.get('elapsed_sec')}s")
    print()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=list(CASES.keys()) + ["all"], default="short")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--no-thinking", action="store_true",
                        help="禁用 enable_thinking (默认 True,与 GrowBox 一致)")
    parser.add_argument("--variant",
                        choices=["sys_only", "user_head", "user_tail", "domain",
                                 "noplan_user", "noplan_sys"],
                        default="sys_only",
                        help="WD 指令注入方式")
    parser.add_argument("--out", default=str(Path(__file__).parent / "results"))
    parser.add_argument("--max-tokens-override", type=int, default=0,
                        help="覆盖 case 默认 max_tokens (0=不覆盖)")
    args = parser.parse_args()
    if args.max_tokens_override > 0:
        for k in CASES:
            CASES[k]["max_tokens"] = args.max_tokens_override

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    targets = list(CASES.keys()) if args.case == "all" else [args.case]
    enable_thinking = not args.no_thinking

    results = []
    for case_key in targets:
        print(f"\n──────── case: {case_key} variant={args.variant} ────────")
        tcs, finish, meta = stream_tool_call(case_key, args.temperature,
                                             enable_thinking, args.variant)
        if tcs is None:
            print(f"  ERROR: {finish} — {meta}", flush=True)
            results.append({"case": case_key, "error": finish, "meta": meta})
            continue
        an = analyze(tcs, finish, meta, case_key)
        an["instr_variant"] = args.variant
        an["enable_thinking"] = enable_thinking
        print_verdict(an)
        results.append(an)

        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        thinking_tag = "thinking" if enable_thinking else "nothink"
        fname = f"{ts}_{case_key}_{args.variant}_{thinking_tag}.json"
        (out_dir / fname).write_text(json.dumps(an, ensure_ascii=False, indent=2))
        print(f"  → {out_dir / fname}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
