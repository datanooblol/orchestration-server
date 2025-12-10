FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# No additional packages needed

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH"

CMD ["/bin/bash"]