FROM python:3.10-slim

WORKDIR /app

# System deps for cryptography and argon2
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libffi-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps (copy everything since pyproject.toml uses -e .)
COPY . .
RUN pip install --no-cache-dir -e .

RUN mkdir -p /app/data/logs

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "-m", "daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
