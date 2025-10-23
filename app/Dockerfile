
# Dockerfile — python 3.11 slim + ffmpeg + pip deps
FROM python:3.11-slim

# не интерактивный режим для apt
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# обновим индекс и установим ffmpeg (минимально).
# --no-install-recommends снижает лишние пакеты.
RUN apt-get update && \
  apt-get install -y --no-install-recommends ffmpeg ca-certificates && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

# Копируем исходники
COPY . /app

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1

# Запуск приложения (подставь нужную команду при необходимости)
CMD ["python", "bot.py"]

