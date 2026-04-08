FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY ./apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy API application and real inference modules
COPY ./apps/api/app ./app
COPY ./src ./src

# Copy trained ONNX model
COPY ./models ./models

EXPOSE 8000

# Create runtime directories
RUN mkdir -p /app/dataset /app/models

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
