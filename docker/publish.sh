#!/usr/bin/env bash
# Publish the frozen evaluation image, so other machines pull the numbers'
# environment instead of rebuilding it.
#
#   docker login                              # once, interactively
#   docker/publish.sh <namespace>             # e.g. houstonzhang
#   W2C_DOCKERHUB_NAMESPACE=yourname docker/publish.sh
#
# What is published is the environment the metrics are defined against - the
# pinned numeric stack and the two networks' weights - which is why a pull
# reproduces this machine's numbers and a rebuild elsewhere would not. Tags: the
# commit the image was built from, and `latest`.
set -euo pipefail
cd "$(dirname "$0")/.."

NAMESPACE="${1:-${W2C_DOCKERHUB_NAMESPACE:-}}"
if [ -z "$NAMESPACE" ]; then
  echo "usage: docker/publish.sh <dockerhub-namespace>" >&2
  exit 1
fi
if [ ! -f "${HOME}/.docker/config.json" ]; then
  echo "not logged in - run 'docker login' first" >&2
  exit 1
fi
if ! docker image inspect w2c-bench:latest >/dev/null 2>&1; then
  echo "w2c-bench:latest not built - run docker/build.sh first" >&2
  exit 1
fi

SHA=$(git rev-parse --short HEAD 2>/dev/null || echo dev)
REMOTE="${NAMESPACE}/w2c-bench"

# An image that cannot even run its own CLI is not worth a 7 GB upload.
echo "checking the image runs..."
docker run --rm "$(docker image inspect -f '{{.Id}}' w2c-bench:latest)" --help >/dev/null

docker tag w2c-bench:latest "${REMOTE}:${SHA}"
docker tag w2c-bench:latest "${REMOTE}:latest"
echo "pushing ${REMOTE}:${SHA} (~$(docker image inspect -f '{{.Size}}' w2c-bench:latest | awk '{printf "%.1fGB", $1/1e9}'))..."
docker push "${REMOTE}:${SHA}"
docker push "${REMOTE}:latest"

# The overview a registry shows is not part of the image, so pushing one without
# it leaves an unexplained multi-gigabyte download on the page.
if [ -n "${DOCKERHUB_TOKEN:-}" ]; then
  echo "updating the Docker Hub description..."
  JWT=$(curl -s -H "Content-Type: application/json" \
    -d "{\"username\":\"${NAMESPACE}\",\"password\":\"${DOCKERHUB_TOKEN}\"}" \
    https://hub.docker.com/v2/users/login/ | python3 -c 'import json,sys; print(json.load(sys.stdin).get("token",""))')
  if [ -n "$JWT" ]; then
    python3 - "$JWT" "$REMOTE" <<'PY'
import json, sys, urllib.request
jwt, remote = sys.argv[1], sys.argv[2]
body = json.dumps({
    "full_description": open("docker/DOCKERHUB.md").read(),
    "description": "Deterministic widget2code benchmark evaluator: 12 quality metrics over a frozen numeric stack.",
}).encode()
request = urllib.request.Request(
    f"https://hub.docker.com/v2/repositories/{remote}/", data=body, method="PATCH",
    headers={"Content-Type": "application/json", "Authorization": f"JWT {jwt}"})
with urllib.request.urlopen(request) as response:
    print("  description updated:", response.status)
PY
  else
    echo "  could not authenticate to the Hub API; paste docker/DOCKERHUB.md into the web UI" >&2
  fi
else
  echo "set DOCKERHUB_TOKEN to also publish docker/DOCKERHUB.md as the overview"
fi

echo
echo "published. On any other machine:"
echo "    docker run --rm -v ...:/gt -v ...:/pred ${REMOTE}:${SHA} --gt_dir /gt --pred_dir /pred"
echo "Pin the digest when it has to be provably the same image:"
docker image inspect -f '{{index .RepoDigests 0}}' "${REMOTE}:${SHA}" 2>/dev/null || true
