#!/bin/bash

# -----------------------------------------------------------------------------
# gpt-4o
# -----------------------------------------------------------------------------
source venv/bin/activate
python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment gpt-4o-test-1000-html-no-size-minimal-cal-size-cal-aspect-ratio \
  --threads 1 --model gpt-4o --include "html-no-size/1-minimal.md" --size --aspect-ratio

source venv/bin/activate
python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment gpt-4o-test-1000-html-no-size-minimal-cal-size \
  --threads 1 --model gpt-4o --include "html-no-size/1-minimal.md" --size

source venv/bin/activate
python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment gpt-4o-test-1000-html-no-size-minimal-cal-aspect-ratio \
  --threads 1 --model gpt-4o --include "html-no-size/1-minimal.md" --aspect-ratio

source venv/bin/activate
python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment gpt-4o-test-1000-html-no-size-minimal \
  --threads 1 --model gpt-4o --include "html-no-size/1-minimal.md"

# -----------------------------------------------------------------------------
# doubao-1.6
# -----------------------------------------------------------------------------
source venv/bin/activate
python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment doubao-seed-1-6-250615-test-1000-html-no-size-minimal-cal-size-cal-aspect-ratio \
  --threads 1 --model doubao-seed-1-6-250615 --include "html-no-size/1-minimal.md" --size --aspect-ratio

source venv/bin/activate
python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment doubao-seed-1-6-250615-test-1000-html-no-size-minimal-cal-size \
  --threads 1 --model doubao-seed-1-6-250615 --include "html-no-size/1-minimal.md" --size

source venv/bin/activate
python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment doubao-seed-1-6-250615-test-1000-html-no-size-minimal-cal-aspect-ratio \
  --threads 1 --model doubao-seed-1-6-250615 --include "html-no-size/1-minimal.md" --aspect-ratio

source venv/bin/activate
python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment doubao-seed-1-6-250615-test-1000-html-no-size-minimal \
  --threads 1 --model doubao-seed-1-6-250615 --include "html-no-size/1-minimal.md"


# -----------------------------------------------------------------------------
# qwen3-vl-235b-a22b-instruct
# -----------------------------------------------------------------------------
python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment qwen3vl-235b-a22b-instruct-test-1000-html-no-size-minimal-cal-size-cal-aspect-ratio \
  --threads 8 --provider openai_compatible --api-key EMPTY --base-url http://202.78.161.193:3050/v1 \
  --model "Qwen/Qwen3-VL-235B-A22B-Instruct" --include "html-no-size/1-minimal.md" \
  --timeout 3600 --max-tokens 2048 --size --aspect-ratio

python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment qwen3vl-235b-a22b-instruct-test-1000-html-no-size-minimal-cal-size \
  --threads 8 --provider openai_compatible --api-key EMPTY --base-url http://202.78.161.193:3050/v1 \
  --model "Qwen/Qwen3-VL-235B-A22B-Instruct" --include "html-no-size/1-minimal.md" \
  --timeout 3600 --max-tokens 2048 --size

python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment qwen3vl-235b-a22b-instruct-test-1000-html-no-size-minimal-cal-aspect-ratio \
  --threads 8 --provider openai_compatible --api-key EMPTY --base-url http://202.78.161.193:3050/v1 \
  --model "Qwen/Qwen3-VL-235B-A22B-Instruct" --include "html-no-size/1-minimal.md" \
  --timeout 3600 --max-tokens 2048 --aspect-ratio

python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment qwen3vl-235b-a22b-instruct-test-1000-html-no-size-minimal \
  --threads 8 --provider openai_compatible --api-key EMPTY --base-url http://202.78.161.193:3050/v1 \
  --model "Qwen/Qwen3-VL-235B-A22B-Instruct" --include "html-no-size/1-minimal.md" \
  --timeout 3600 --max-tokens 2048


# -----------------------------------------------------------------------------
# qwen3-vl-plus
# -----------------------------------------------------------------------------
python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment qwen3vl-plus-test-1000-html-no-size-minimal-cal-size-cal-aspect-ratio \
  --threads 1 --model qwen3-vl-plus --include "html-no-size/1-minimal.md" --size --aspect-ratio

python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment qwen3vl-plus-test-1000-html-no-size-minimal-cal-size \
  --threads 1 --model qwen3-vl-plus --include "html-no-size/1-minimal.md" --size

python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment qwen3vl-plus-test-1000-html-no-size-minimal-cal-aspect-ratio \
  --threads 1 --model qwen3-vl-plus --include "html-no-size/1-minimal.md" --aspect-ratio

python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment qwen3vl-plus-test-1000-html-no-size-minimal \
  --threads 1 --model qwen3-vl-plus --include "html-no-size/1-minimal.md"


# -----------------------------------------------------------------------------
# gemini-2.5-pro
# -----------------------------------------------------------------------------
source venv/bin/activate
python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment gemini-2.5-pro-test-1000-html-no-size-minimal-cal-size-cal-aspect-ratio \
  --threads 1 --model gemini-2.5-pro --include "html-no-size/1-minimal.md" --size --aspect-ratio

source venv/bin/activate
python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment gemini-2.5-pro-test-1000-html-no-size-minimal-cal-size \
  --threads 1 --model gemini-2.5-pro --include "html-no-size/1-minimal.md" --size

source venv/bin/activate
python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment gemini-2.5-pro-test-1000-html-no-size-minimal-cal-aspect-ratio \
  --threads 1 --model gemini-2.5-pro --include "html-no-size/1-minimal.md" --aspect-ratio

source venv/bin/activate
python scripts/batch_infer.py --images-dir /shared/zhixiang_team/widget_research/images/images-test-1000 \
  --experiment gemini-2.5-pro-test-1000-html-no-size-minimal \
  --threads 1 --model gemini-2.5-pro --include "html-no-size/1-minimal.md"