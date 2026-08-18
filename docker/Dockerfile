# Frozen evaluation environment: the metric values are defined by this image.
#
# Everything the numbers depend on is baked in and pinned - Python, the numeric
# stack, the two neural nets (EasyOCR's detector/recogniser and LPIPS's VGG
# trunk) and their weights. The host contributes CPU and the mounted filesystem,
# nothing else.
#
# torch is the same +cu130 build the 0.2.9 numbers were produced with, so both
# execution paths are available and neither is a reimplementation:
#
#   default   CPU. Reproducible on any machine - this is what the shipped GT
#             cache and the golden values are defined against.
#   --cuda    GPU. Fast, and the path the published 0.2.9 tables came from, but
#             cuDNN selects kernels by architecture and autotunes by timing, so
#             it can only be trusted once the self-check has confirmed it agrees
#             with the CPU golden on this particular machine.
#
# LAYER ORDER IS THE CONTRACT. Everything above `COPY src/` is the environment
# layer and must not be rebuilt casually - re-resolving it is what reintroduces
# drift. Code changes only invalidate the last two layers.
FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="w2c-bench" \
      org.opencontainers.image.description="Deterministic widget2code benchmark evaluator: 12 quality metrics over a frozen CPU numeric stack, with a per-host golden self-check." \
      org.opencontainers.image.licenses="Apache-2.0"

# opencv-python-headless still wants libgomp; nothing here needs libGL.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# The exact torch build of the 0.2.9 environment. Using the CUDA build for the
# CPU path too is deliberate: a +cpu wheel is a different binary, and matching
# 0.2.9 matters more than the 4.5 GB the CUDA stack costs.
COPY docker/constraints-cuda.txt /tmp/constraints-cuda.txt
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cu130 \
        --extra-index-url https://pypi.org/simple \
        -c /tmp/constraints-cuda.txt \
        torch==2.11.0 torchvision==0.26.0 \
    && rm /tmp/constraints-cuda.txt

COPY docker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Model weights are staged by docker/build.sh from the host caches, then checked
# against docker/weights.sha256. Baking them in is what makes a run offline and
# keeps a silent upstream re-release from changing the metrics.
#
# user_network/ is created here on purpose: EasyOCR makedirs it on startup, and
# the container runs as the invoking host user, who cannot write under /opt.
ENV TORCH_HOME=/opt/models/torch \
    EASYOCR_MODULE_PATH=/opt/models/easyocr
COPY docker/weights/ /tmp/weights/
COPY docker/weights.sha256 /tmp/weights.sha256
RUN cd /tmp/weights && sha256sum -c /tmp/weights.sha256 \
    && mkdir -p ${TORCH_HOME}/hub/checkpoints ${EASYOCR_MODULE_PATH}/model \
                ${EASYOCR_MODULE_PATH}/user_network \
    && mv vgg16-397923af.pth ${TORCH_HOME}/hub/checkpoints/ \
    && mv craft_mlt_25k.pth english_g2.pth ${EASYOCR_MODULE_PATH}/model/ \
    && rm -rf /tmp/weights /tmp/weights.sha256 \
    && chmod -R a+rX /opt/models

# One thread per process. BLAS and oneDNN change their reduction order with the
# thread count, and OpenCV's own pool does the same; parallelism belongs at the
# process level, where each pair is independent and the arithmetic is untouched.
# These bind the CPU path only - the GPU path is governed by the self-check.
# OpenCV needs its own variable: it runs a pool of its own that the OMP/BLAS
# variables do not reach, and it defaults to one thread per core. Measured in
# this image, cv2.getNumThreads() reported 240 with only the OMP caps set.
ENV OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    OPENCV_FOR_THREADS_NUM=1 \
    PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /opt/w2c-bench
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir --no-deps .

# The cache builder and the comparison helpers ship with the image: the point of
# freezing the environment is that the intermediates are generated inside it.
COPY tools/ tools/

# Identifies this exact build; the self-check marker is keyed on it, so a machine
# re-proves itself iff the image actually changed.
ARG BUILD_STAMP=dev
ENV W2C_BENCH_STAMP=${BUILD_STAMP}

ENTRYPOINT ["widget2code-bench-exp"]
CMD ["--help"]
