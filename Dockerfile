FROM python:3.12-slim

# util-linux: provides the mountpoint binary used by health checks
# gosu: lightweight privilege dropping (Debian equivalent of su-exec)
RUN apt-get update && apt-get install -y --no-install-recommends \
    util-linux \
    gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN mkdir -p /app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

EXPOSE 8222

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "app.py"]