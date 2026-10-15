FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir "prefect>=3,<4"

COPY dummy_flow.py .

CMD ["python", "dummy_flow.py"]