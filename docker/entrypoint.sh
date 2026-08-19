#!/bin/bash
# How the container decides what to run:
#   no arguments          the service mode: self-check, then the supervised
#                         single-pair daemon (the reward path)
#   first argument is -*  the CLI: forwarded to widget2code-bench-exp, so
#                         `docker run <image> --gt_dir ... --pred_dir ...`
#                         is the batch mode and --gt_image/--pred_image the
#                         single mode
#   anything else         executed verbatim (widget2code-bench-exp, bash, ...)
set -e

if [ "$#" -eq 0 ]; then
    CUDA_ARG=
    if [ "${W2C_BENCH_CUDA:-0}" = 1 ]; then CUDA_ARG=--cuda; fi
    python docker/selfcheck.py --cached $CUDA_ARG
    exec python -m widget2code_bench.supervisor --workers "${W2C_BENCH_WORKERS:-8}" $CUDA_ARG
fi

case "$1" in
    -*) exec widget2code-bench-exp "$@" ;;
    *)  exec "$@" ;;
esac
