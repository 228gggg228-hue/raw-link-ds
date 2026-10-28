FROM python:3.11-slim

# Утилиты для распаковки RAR (rarfile сам архивы не читает)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libarchive-tools \
    unar \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
