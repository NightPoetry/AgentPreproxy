#!/usr/bin/env python3
"""
LoRA 微调 Gemma 3 1B：训练看门狗计数 Tag 能力
使用 Python API 绕过 MPI 冲突
"""
import os
os.environ["MLX_DISABLE_MPI"] = "1"

from pathlib import Path

MODEL_PATH = "/Volumes/nightpoetry/.lmstudio/models/mlx-community/gemma-3-1b-it-qat-4bit"
DATA_DIR = str(Path(__file__).parent / "data")
ADAPTER_DIR = str(Path(__file__).parent / "adapters")

Path(ADAPTER_DIR).mkdir(exist_ok=True)

print("加载模型...")
from mlx_lm import lora

args = lora.build_parser().parse_args([
    "--model", MODEL_PATH,
    "--data", DATA_DIR,
    "--train",
    "--adapter-path", ADAPTER_DIR,
    "--iters", "200",
    "--batch-size", "1",
    "--num-layers", "8",
    "--learning-rate", "1e-4",
    "--steps-per-report", "10",
    "--steps-per-eval", "50",
    "--seed", "42",
    "--fine-tune-type", "lora",
])

print(f"模型: {MODEL_PATH}")
print(f"数据: {DATA_DIR}")
print(f"输出: {ADAPTER_DIR}")
print("=" * 60)

lora.run(args)

print("\n✓ 微调完成！")
print(f"适配器: {ADAPTER_DIR}")
