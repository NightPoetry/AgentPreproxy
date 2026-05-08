# 实验五：LoRA 微调——Tag 能力内化

**目的：** 验证"先提示词，后训练内化"的路径——能否通过少量训练让 1B 模型学会正确的 Tag 递增计数。

**基础模型：** Gemma 3 1B (4bit QAT MLX, 736MB)
**训练框架：** MLX LoRA
**训练数据：** 8 条样本（烹饪/体育/历史/音乐/园艺/天文），**与测试内容零重叠**
**测试内容：** 机器学习解释、修仙小说（训练中完全未见过）

## 三版训练对照

| 版本 | 目录 | 迭代 | LoRA层 | 学习率 | 小说 Tag | 小说内容 | 评价 |
|------|------|------|--------|--------|---------|---------|------|
| 欠拟合 | `checkpoints/50iter/` | 50 | 4 | 5e-5 | ✗ 无 | ✗ 崩溃 | Tag 没学会 |
| **★ 推荐** | **`checkpoints/100iter_推荐/`** | **100** | **4** | **8e-5** | **WD:1→7** | **有内容** | **最佳平衡** |
| 过拟合 | `checkpoints/300iter/` | 300 | 8 | 1e-4 | ✗ 无 | ✗ 碎片 | Tag 挤掉了内容 |

## ★ 推荐版本（100 iter）的关键表现

小说测试展示了**完整的渐进退化光谱**：
1. WD:1→7 正确递增 + 内容正常 → 注意力在场
2. WD:7 后 Tag 消失 + 内容开始重复 → 注意力退化
3. 第二轮 Tag 格式错乱 → 注意力彻底塌

**Tag 退化先于内容崩溃出现——这使 Tag 成为注意力涣散的早期预警信号。**

## 复现步骤

```bash
# 1. 生成训练数据
python generate_data.py

# 2. 训练（修改 --iters 切换版本）
python -m mlx_lm lora \
  --model <gemma-3-1b路径> \
  --data data/ --train --fine-tune-type lora \
  --adapter-path checkpoints/100iter_推荐/ \
  --iters 100 --batch-size 1 --num-layers 4 \
  --learning-rate 8e-5 --seed 42

# 3. 测试
python -m mlx_lm generate \
  --model <gemma-3-1b路径> \
  --adapter-path checkpoints/100iter_推荐/ \
  --max-tokens 500 --prompt "<测试prompt>"
```

## 文件说明

| 路径 | 说明 |
|------|------|
| `generate_data.py` | 干净版数据生成脚本（与测试零重叠） |
| `train.py` | 训练启动脚本 |
| `data/` | 训练/验证数据 (8 train / 2 valid) |
| `checkpoints/50iter/` | 欠拟合版权重 |
| **`checkpoints/100iter_推荐/`** | **★ 推荐版权重** |
| `checkpoints/300iter/` | 过拟合版权重 |
| `gemma3_1b/对照结果.md` | 三版训练的详细对照测试结果 |
