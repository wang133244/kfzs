FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/vendor/chroma-onnx/all-MiniLM-L6-v2 /root/.cache/chroma/onnx_models/all-MiniLM-L6-v2

COPY backend/app ./app

EXPOSE 8000

CMD ["python", "-m", "app.run"]
