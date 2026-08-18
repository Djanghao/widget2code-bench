#!/usr/bin/env bash
# Prove the image reproduces the host evaluation, on this machine.
#
#   tools/verify_image.sh [N_SAMPLES] [GT_DIR] [PRED_DIR] [PRED_NAME]
#
# Runs the same samples twice - once against the 0.2.9 install on the host, once
# inside w2c-bench - and compares every metric of every sample. Both runs are
# held to one thread per worker so the comparison is about the environment, not
# about how busy the machine was.
#
# Needs a machine that is not already oversubscribed: the evaluator is CPU bound,
# and a host above its core count will simply starve both runs.
set -euo pipefail
cd "$(dirname "$0")/.."

N="${1:-20}"
GT="${2:-/shared/houston/workspace/widget2code-emnlp/data/widget2code-benchmark/test}"
PRED="${3:-/shared/houston/workspace/widget2code-grpo/output/eval_test_9b_2ep}"
PRED_NAME="${4:-rendered.png}"
HOST_PY="${HOST_PY:-/shared/houston/miniconda3/envs/widget2code-bench-exp/bin/python}"
IMAGE="${IMAGE:-w2c-bench:latest}"
WORK="${WORK:-$(mktemp -d)}"

echo "==> staging $N samples into $WORK"
mkdir -p "$WORK"/{gt,pred_host,pred_ctr}
python3 - "$WORK" "$GT" "$PRED" "$PRED_NAME" "$N" <<'PY'
import os, sys, shutil
from PIL import Image
work, gt, pred, pred_name, n = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
picked = []
for d in sorted(os.listdir(pred)):
    p, g = f"{pred}/{d}/{pred_name}", f"{gt}/{d}.png"
    if os.path.exists(p) and os.path.exists(g):
        picked.append(d)
    if len(picked) >= n:
        break
for d in picked:
    shutil.copy(f"{gt}/{d}.png", f"{work}/gt/{d}.png")
    for side in ("pred_host", "pred_ctr"):
        os.makedirs(f"{work}/{side}/{d}", exist_ok=True)
        shutil.copy(f"{pred}/{d}/{pred_name}", f"{work}/{side}/{d}/{pred_name}")
print(f"    {len(picked)} samples")
PY

echo "==> host run (widget2code-bench-exp 0.2.9, CPU)"
env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= \
    "$HOST_PY" -m widget2code_bench.main \
    --gt_dir "$WORK/gt" --pred_dir "$WORK/pred_host" --pred_name "$PRED_NAME" \
    --output_dir "$WORK/out_host" --workers 8 --minimal > "$WORK/host.log" 2>&1

echo "==> container run ($IMAGE, CPU)"
docker run --rm --user "$(id -u):$(id -g)" \
    -e HOME=/tmp -e USER=w2c -e MPLCONFIGDIR=/tmp/mpl \
    -v "$WORK:/data" "$IMAGE" \
    --gt_dir /data/gt --pred_dir /data/pred_ctr --pred_name "$PRED_NAME" \
    --output_dir /data/out_ctr --workers 8 --minimal > "$WORK/ctr.log" 2>&1

echo "==> comparing"
python3 tools/compare_eval.py "$WORK/pred_host" "$WORK/pred_ctr" || {
    echo
    echo "not bit-identical; re-checking at 4 decimals"
    python3 tools/compare_eval.py "$WORK/pred_host" "$WORK/pred_ctr" --decimals 4
}
echo
echo "work dir kept at $WORK"
