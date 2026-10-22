ARG PYTHON_VERSION=3.12

FROM artefact.skao.int/ska-build-python-ubuntu26:1.1.1 AS buildenv
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

FROM artefact.skao.int/ska-python-ubuntu26:1.1.1 AS runtime

RUN apt-get update && apt-get install -y rclone

# Best practice not to run as root
RUN useradd ska-dlm
USER ska-dlm

# Copy all Python packages & console scripts to the runtime container
COPY --from=buildenv /app/.venv /app/.venv/
ENV PATH="/app/.venv/bin:${PATH}"

