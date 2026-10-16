FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/workspace
WORKDIR /workspace
COPY backend/requirements.lock /workspace/backend/requirements.lock
RUN pip install --no-cache-dir -r backend/requirements.lock && pip check
COPY backend /workspace/backend
COPY data/initialization.sql /workspace/data/initialization.sql
COPY data/migrations /workspace/data/migrations
CMD ["python", "-m", "backend.flow", "replay"]
