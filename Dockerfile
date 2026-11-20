FROM artefact.skao.int/ska-build-python-ubuntu24:1.1.5 AS buildenv
WORKDIR /app

# Cache main dependencies
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.in-project true \
    && poetry env use python3.12 \
    && poetry install --only main --no-root

COPY ./ ./
RUN . .venv/bin/activate \
    && pip install --no-deps .

FROM artefact.skao.int/ska-python-ubuntu24:1.1.5 AS runtime

RUN apt-get update && apt-get install -y rclone

# Best practice not to run as root
RUN useradd -ms /bin/bash ska-dlm
USER ska-dlm

# Copy all Python packages & console scripts to the runtime container
COPY --from=buildenv /app/.venv /app/.venv/
ENV PATH="/app/.venv/bin:${PATH}"
