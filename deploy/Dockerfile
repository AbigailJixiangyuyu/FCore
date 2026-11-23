FROM python:3.10-slim-bookworm AS base
WORKDIR /opt/fcore/backend
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

FROM base AS build
RUN apt-get update && apt-get install -y --no-install-recommends g++ && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir uv==0.11.8
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --locked --no-dev --no-install-project --python /usr/local/bin/python3.10 \
    && uv pip install --python .venv/bin/python "torch @ https://download-r2.pytorch.org/whl/cpu/torch-2.8.0%2Bcpu-cp310-cp310-manylinux_2_28_x86_64.whl#sha256=16d75fa4e96ea28a785dfd66083ca55eb1058b6d6c5413f01656ca965ee2077e"
COPY backend/algorithms ./algorithms
COPY backend/app ./app
COPY backend/scripts ./scripts
COPY backend/vendor/parallel-kcore ./vendor/parallel-kcore
RUN python -m scripts.build_parallel_core

FROM base
ENV PATH="/opt/fcore/backend/.venv/bin:${PATH}" FCORE_DEVICE=cpu OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 libgomp1 && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 fcore \
    && install -d -o fcore -g fcore /opt/fcore/data /opt/fcore/exports
COPY --from=build /opt/fcore/backend/.venv ./.venv
COPY --from=build /opt/fcore/backend/.native ./.native
COPY --from=build /opt/fcore/backend/algorithms ./algorithms
COPY --from=build /opt/fcore/backend/app ./app
COPY backend/pyproject.toml ./
COPY config /opt/fcore/config
COPY frontend/dist /opt/fcore/frontend/dist
COPY --chown=fcore:fcore data /opt/fcore/data
COPY models /opt/fcore/models
USER fcore
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD ["python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/api/health', timeout=4).close()"]
CMD ["fastapi", "run", "--host", "0.0.0.0", "--port", "8000"]
