FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml .
COPY config.py params.py job.py ./

RUN pip install --no-cache-dir .

CMD ["python3"]
