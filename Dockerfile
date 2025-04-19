FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    build-essential libpq-dev curl gettext nginx python3-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

COPY requirements*.txt /code/
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . /code/

EXPOSE 8000

CMD ["bash", "./runs.sh", "--dev"]
