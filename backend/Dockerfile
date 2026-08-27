FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY backend/requirements.txt ./backend-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r backend-requirements.txt azure-identity

COPY dqeval/ ./dqeval/
COPY dq_pipeline/ ./dq_pipeline/
COPY main.py ./main.py
COPY results_collector.py ./results_collector.py
COPY backend/ ./backend/

ENV DQ_PIPELINE_DIR=/app
EXPOSE 8000
WORKDIR /app/backend
CMD ["python", "-m", "uvicorn", "main_api:app", "--host", "0.0.0.0", "--port", "8000"]