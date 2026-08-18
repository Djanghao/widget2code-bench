#!/usr/bin/env bash
# Run the self-checking benchmark daemon over /tmp/w2c-bench/bench.sock.
#
#   docker/run.sh [workers]
#   W2C_BENCH_CUDA=1 docker/run.sh 1
set -euo pipefail

WORKERS="${1:-8}"
NAME=w2c-bench
IMAGE="${W2C_BENCH_IMAGE:-w2c-bench:latest}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "pulling $IMAGE ..."
  docker pull "$IMAGE"
fi

mkdir -p /tmp/w2c-bench
docker rm -f "$NAME" 2>/dev/null || true
rm -f /tmp/w2c-bench/bench.sock /tmp/w2c-bench/heartbeat.json

GPU_ARGS=()
if [ "${W2C_BENCH_CUDA:-0}" = 1 ]; then
  GPU_ARGS+=(--gpus all -e W2C_BENCH_CUDA=1)
fi

docker run -d --name "$NAME" \
  --restart unless-stopped \
  --init \
  --shm-size=2g \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -e USER="$(id -un)" \
  -e LOGNAME="$(id -un)" \
  -e W2C_BENCH_WORKERS="$WORKERS" \
  "${GPU_ARGS[@]}" \
  -v /tmp/w2c-bench:/tmp/w2c-bench \
  "$IMAGE"

echo "waiting for self-check + daemon..."
for _ in $(seq 1 600); do
  if [ -S /tmp/w2c-bench/bench.sock ]; then
    echo "benchmark daemon is up: /tmp/w2c-bench/bench.sock"
    exit 0
  fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null)" != "true" ]; then
    echo "container exited - self-check failed or crash:" >&2
    docker logs "$NAME" | tail -30 >&2
    exit 1
  fi
  sleep 1
done
echo "daemon did not come up within 600s; docker logs $NAME" >&2
exit 1
