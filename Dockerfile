ARG PYTHON_VERSION=3.10

FROM python:${PYTHON_VERSION} AS buildenv
ARG POETRY_VERSION=1.8.2
RUN pip install poetry==${POETRY_VERSION}

WORKDIR /app
COPY ./ ./
RUN poetry config virtualenvs.in-project true \
    && poetry install --only main --no-root \
    && . .venv/bin/activate \
    && pip install --no-deps .

FROM python:${PYTHON_VERSION}-slim AS runtime

RUN apt-get update && apt-get install -y \
    rclone \
    && rm -rf /var/lib/apt/lists/*

# Best practice not to run as root
# RUN useradd meta-gen
# USER meta-gen

# Copy all Python packages & console scripts to our runtime container
COPY --from=buildenv /app/.venv /app/.venv/
ENV PATH="/app/.venv/bin:${PATH}"

# ENTRYPOINT ["meta-gen"]
