FROM python:3.10-slim

# Устанавливаем unrar для работы библиотеки rarfile
RUN apt-get update && apt-get install -y unrar-free && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
