FROM python:3.13-slim AS base

# Install hledger static binary
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -sL https://github.com/simonmichael/hledger/releases/latest/download/hledger-linux-x64.tar.gz \
       | tar -xzv -C /usr/local/bin/ hledger \
    && chmod +x /usr/local/bin/hledger \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source and reinstall (picks up entry points)
COPY src/ src/
RUN pip install --no-cache-dir -e .

# Copy journal data
COPY journal/ journal/

ENV FINANCE_ROOT=/app

EXPOSE 8000

CMD ["fin-mcp", "--http"]
