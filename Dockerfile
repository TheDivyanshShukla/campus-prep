# Use a specialized uv image for faster builds
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    # LaTeX dependencies for PDF generation
    texlive-latex-base \
    texlive-fonts-recommended \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies into the system environment (no venv)
# This prevents volume shadowing issues when mounting the host directory
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv pip install --system --requirement pyproject.toml

# Install Playwright browsers (into system)
# We do this BEFORE copying the project files to leverage Docker's layer caching
# This ensures that browser downloading only happens when pyproject.toml or uv.lock changes
RUN python -m playwright install --with-deps chromium

# Copy project files
COPY . .

# Prepare static and media dirs
RUN mkdir -p staticfiles media

# Setup entrypoint
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
