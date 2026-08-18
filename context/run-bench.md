# 运行 widget2code-bench-exp

## 环境

```bash
conda activate widget2code-bench-exp-0.2.9
```

已装 `widget2code-bench-exp==0.2.9`，CLI = `widget2code-bench-exp`。

## 完整 eval + bad_cases

```bash
CUDA_VISIBLE_DEVICES=7 widget2code-bench-exp \
  --gt_dir /shared/zhixiang_team/widget_research/Comparison/GT \
  --pred_dir /path/to/pred_dir \
  --pred_name output.png \
  --output_dir /path/to/pred_dir/.analysis-0.2.9 \
  --workers 38 \
  --bad_workers 64 \
  --bad_per_metric 20 \
  --cuda
```

- `--workers 38`：eval 阶段并行评估 GT/pred 的线程数
- `--bad_workers 64`：bad_cases 阶段复制+viz 的**进程**数（绕过 GIL）
- `--bad_per_metric 20`：每个 metric 保留最差的 N 个样本

## 只重做 analysis（evaluation.json 已存在时）

```bash
widget2code-bench-exp \
  --gt_dir /shared/zhixiang_team/widget_research/Comparison/GT \
  --pred_dir /path/to/pred_dir \
  --output_dir /path/to/pred_dir/.analysis-0.2.9 \
  --bad_workers 64 --bad_per_metric 20 --skip_eval
```

- `--skip_eval`：跳过 eval，复用每个 sample 已有的 `evaluation/evaluation.json`，只重新生成 `metrics/` xlsx 和 `bad_cases/`

## 跳过 viz / bad_cases（最快）

```bash
widget2code-bench-exp ... --minimal
```

- `--minimal`：不生成 bad_cases 和 viz（只产 `metrics/` 汇总）

## 两张 GPU 并行跑两个数据集

```bash
tmux new -d -s run1 "CUDA_VISIBLE_DEVICES=6 widget2code-bench-exp --gt_dir <GT> --pred_dir <A> --output_dir <A>/.analysis-0.2.9 --workers 38 --bad_workers 64 --bad_per_metric 20 --cuda 2>&1 | tee /tmp/run1.log"
tmux new -d -s run2 "CUDA_VISIBLE_DEVICES=7 widget2code-bench-exp --gt_dir <GT> --pred_dir <B> --output_dir <B>/.analysis-0.2.9 --workers 38 --bad_workers 64 --bad_per_metric 20 --cuda 2>&1 | tee /tmp/run2.log"
tmux ls   # 看进度用 tmux attach -t runN，Ctrl+b d 脱离
```

## 产出结构

```
<pred_dir>/
├── <sample>/evaluation/
│   ├── evaluation.json         # 12 个 metric 分数
│   └── ocr.json                # 缓存给 bad_cases viz 用
├── evaluation.xlsx             # eval 阶段 summary
└── .analysis-0.2.9/
    ├── metrics/
    │   ├── metrics_stats.json
    │   ├── metrics.xlsx        # 4 行 combined（raw/black/white/zero）
    │   ├── raw/<run>-raw-0.2.9.xlsx
    │   ├── black/…
    │   ├── white/…
    │   └── zero/…
    └── bad_cases/              # 非 --minimal 时才有
        ├── <Metric>/
        │   ├── <rank>_score<s>_<sample>/   # 整目录 copy + evaluation/viz/<Metric>.png
        │   └── _scores.txt
        └── _catastrophic_5plus/            # 如有
            ├── bad05_<sample>/
            └── _summary.txt
```
