# syntax=docker/dockerfile:1.7
#
# Dhuan Detective backend image.
#
# Build context is the REPOSITORY ROOT (not backend/), because the image needs
# both backend/ and the repo-level fixtures/demo/ directory that demo mode reads.
# SAM is configured accordingly in infra/template.yaml (DockerContext: ..).
#
#   docker build -f backend/Dockerfile --target lambda -t dhuan-backend:lambda .
#
# Targets:
#   lambda   - production AWS Lambda image (arm64). CMD dispatches on the CMD
#              env var: "pipeline" for Step Functions tasks, otherwise Mangum
#              serves the FastAPI app.
#   dev      - the same image running uvicorn, for local use.
#
# Dependencies come from the committed uv.lock via `uv export`, installed into
# /opt/python and exposed via PYTHONPATH rather than a venv: the builder's
# interpreter lives at /usr/local/bin/python3.12 while the Lambda base image's
# lives at /var/lang/bin/python3.12, so a copied venv has dangling symlinks.
# Installing into a plain directory sidesteps that, and is the pattern the AWS
# base images are designed for.

# --------------------------------------------------------------- builder ----
FROM python:3.12-slim-bookworm AS builder

ARG UV_VERSION=0.5.11

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/usr/local/bin:${PATH}"

RUN pip install --no-cache-dir "uv==${UV_VERSION}"

WORKDIR /build

# Resolve the pinned dependency set first so this layer caches on lock changes.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv export --frozen --no-dev --extra agents --no-emit-project \
        --format requirements-txt --no-hashes -o /tmp/requirements.txt \
 && uv pip install --target /opt/python --no-cache -r /tmp/requirements.txt

# Application source, model artifact, real data snapshot and demo recordings.
COPY backend/src ./src
COPY backend/models ./models
COPY backend/data ./data
COPY fixtures/demo ./demo_data

# --------------------------------------------------------------- runtime ----
FROM public.ecr.aws/lambda/python:3.12-arm64 AS lambda

ENV PYTHONPATH="/opt/python:/var/task/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DHUAN_MODEL_DIR=/var/task/models \
    DHUAN_DATA_DIR=/var/task/data \
    DEMO_DATA_DIR=/var/task/demo_data \
    AWS_EXECUTION_ENV=AWS_Lambda_python3.12

WORKDIR ${LAMBDA_TASK_ROOT}

COPY --from=builder /opt/python /opt/python
COPY --from=builder /build/src ./src
COPY --from=builder /build/models ./models
COPY --from=builder /build/data ./data
COPY --from=builder /build/demo_data ./demo_data

# Mangum for the API; CMD=pipeline routes to the Step Functions task handlers.
COPY backend/lambda_handler.py ./

CMD ["lambda_handler.handler"]

# ------------------------------------------------------------------ dev -----
FROM lambda AS dev
EXPOSE 8080
CMD ["dhuan.api.app:app"]