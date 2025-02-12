ARG PYTHON_VERSION=3.10

FROM python:${PYTHON_VERSION} AS buildenv
ARG POETRY_VERSION=1.8.2
RUN pip install poetry==${POETRY_VERSION}

WORKDIR /app

# Cache main dependencies
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.in-project true \
    && poetry install --only main --no-root

COPY ./ ./
RUN . .venv/bin/activate \
    && pip install --no-deps .

FROM python:${PYTHON_VERSION}-slim AS runtime

RUN apt-get update && apt-get install -y rclone

# Best practice not to run as root
RUN useradd ska-dlm
USER ska-dlm

# Copy all Python packages & console scripts to the runtime container
COPY --from=buildenv /app/.venv /app/.venv/
ENV PATH="/app/.venv/bin:${PATH}"

CMD ["ska-dlm-sm-service"]
