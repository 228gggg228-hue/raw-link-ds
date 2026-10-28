FROM python:3.10-slim

# Устанавливаем bsdtar (libarchive-tools) для распаковки RAR
RUN apt-get update && apt-get install -y libarchive-tools && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
