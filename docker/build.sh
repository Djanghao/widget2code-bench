#!/usr/bin/env bash
# Build the frozen evaluation image. Build ONCE on one machine and distribute the
# image itself (docker push, or docker save | docker load) - rebuilding per
# machine re-resolves the dependency layers and reintroduces the drift the image
# exists to prevent.
set -euo pipefail
cd "$(dirname "$0")/.."

SHA=$(git rev-parse --short HEAD 2>/dev/null || echo dev)
STAMP="${SHA}-$(date +%Y%m%d%H%M%S)"
TAG="w2c-bench:${SHA}"

# EasyOCR and LPIPS fetch their weights on first use. Baking them in is what
# makes a run offline and pins the metrics to a known set of parameters, so the
# build stages them from the host caches and the Dockerfile checks their hashes.
STAGE=docker/weights
mkdir -p "$STAGE"
declare -A SRC=(
  [craft_mlt_25k.pth]="$HOME/.EasyOCR/model/craft_mlt_25k.pth"
  [english_g2.pth]="$HOME/.EasyOCR/model/english_g2.pth"
  [vgg16-397923af.pth]="$HOME/.cache/torch/hub/checkpoints/vgg16-397923af.pth"
)
for name in "${!SRC[@]}"; do
  if [[ ! -f "$STAGE/$name" ]]; then
    src="${SRC[$name]}"
    [[ -f "$src" ]] || { echo "missing weight: $src" >&2; exit 1; }
    echo "staging $name ..."
    cp "$src" "$STAGE/$name"
  fi
done
( cd "$STAGE" && sha256sum -c ../weights.sha256 )

# --network=host: this machine's docker bridge has no DNS, so RUN steps cannot
# resolve pypi/deb mirrors on the default build network.
docker build --network=host -f docker/Dockerfile --build-arg BUILD_STAMP="$STAMP" \
    -t "$TAG" -t w2c-bench:latest .

echo
echo "built $TAG"
docker images w2c-bench | head -3
