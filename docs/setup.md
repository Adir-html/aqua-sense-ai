# Setup Guide

## Prerequisites

- **Python 3.9+** (for training)
- **Docker & Docker Compose** (for local development)
- **Git** (for version control)
- Optional: **CUDA toolkit** (for GPU acceleration)

## Local Development Setup

### 1. Clone Repository

```bash
git clone <repo-url>
cd aqua-sense-ai
```

### 2. Start Services with Docker Compose

```bash
# Build and start all services
docker compose up --build

# Services will be available at:
# - Web: http://localhost:3000
# - API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

### 3. Verify Deployment

```bash
# Check API health
curl http://localhost:8000/health

# Check web health
curl http://localhost:3000/health

# Check model readiness
curl http://localhost:8000/inference/health
```

## Setting Up Model Training

### 1. Prepare Dataset

Create image folders:
```bash
mkdir -p dataset/normal
mkdir -p dataset/faulty
```

Add images:
- `dataset/normal/` — Images of properly functioning irrigation systems
- `dataset/faulty/` — Images of faulty/clogged systems

Recommended:
- At least 50 images per class
- 200+ images per class for better accuracy
- Equal distribution between classes

### 2. Install Training Dependencies

Option A: Direct installation
```bash
pip install torch torchvision pillow numpy scikit-learn matplotlib onnxruntime
```

Option B: Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install torch torchvision pillow numpy scikit-learn matplotlib onnxruntime
```

### 3. Train Model

1. Open `notebooks/train_model.ipynb` in Jupyter
2. Install Jupyter if needed:
   ```bash
   pip install jupyter
   jupyter notebook
   ```
3. Run through cells in order:
   - Section 1: Setup imports
   - Section 2: Load dataset
   - Section 3: Data augmentation
   - Section 4: Model definition
   - Section 5: Training (main loop)
   - Section 6: Evaluation
   - Section 7: ONNX export
4. Model saved to `models/model.onnx`

### 4. Deploy Trained Model

```bash
# Set environment variables
export MODEL_PATH=models/model.onnx
export MODEL_FRAMEWORK=onnx

# Restart API to load model
docker compose restart api
```

Or in `.env` file:
```dotenv
MODEL_PATH=models/model.onnx
MODEL_FRAMEWORK=onnx
```

## Configuration

### Environment Variables

Create `.env` from `.env.example`:
```bash
cp .env.example .env
```

Edit `.env`:
```dotenv
# Model
MODEL_PATH=models/model.onnx
MODEL_FRAMEWORK=onnx

# API
API_KEY=optional-secret-key
RATE_LIMIT_PER_MIN=100
ALLOW_RAW_UPLOADS=false

# Storage (optional)
S3_BUCKET=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=

# Web
WEB_PORT=3000
API_URL=http://localhost:8000
```

## Development Workflow

### Running Services Separately

**Terminal 1: Web Service**
```bash
cd apps/web
docker build -t aqua-web .
docker run -p 3000:80 aqua-web
```

**Terminal 2: API Service**
```bash
cd apps/api
docker build -t aqua-api .
docker run -p 8000:8000 --env-file ../../.env aqua-api
```

### Local Python API (Without Docker)

```bash
cd apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Testing Inference

```bash
# Using test script
python scripts/verify_api.py

# Using post_demo_image.py
python scripts/post_demo_image.py

# Using curl
curl -X POST -F "file=@test.jpg" http://localhost:8000/analyze
```

## Troubleshooting

### Model Not Loading

Check logs:
```bash
docker compose logs api
```

**Issue**: `MODEL_PATH not found`
- Verify file exists: `ls -la models/model.onnx`
- Check environment variable is set
- Restart API: `docker compose restart api`

**Issue**: `onnxruntime not installed`
- Add to `requirements.txt`
- Rebuild container: `docker compose up --build api`

### GPU/CUDA Issues

To use GPU with ONNX:
```bash
pip install onnxruntime-gpu
```

Set in `.env`:
```dotenv
ONNX_EXECUTION_PROVIDERS=CUDAExecutionProvider,CPUExecutionProvider
```

### Port Already in Use

Change ports in `docker-compose.yml`:
```yaml
web:
  ports:
    - "3001:80"  # Changed from 3000
api:
  ports:
    - "8001:8000"  # Changed from 8000
```

### CORS Errors

Ensure web frontend can reach API:
- Check `apps/api/app/main.py` CORS configuration
- Default allows `http://localhost:3000`
- For production, update allowed origins

## Production Deployment

### Docker Build

```bash
# Build images
docker build -t aqua-web apps/web/
docker build -t aqua-api -f apps/api/Dockerfile .

# Tag for registry
docker tag aqua-web registry.example.com/aqua-web:1.0.0
docker tag aqua-api registry.example.com/aqua-api:1.0.0

# Push to registry
docker push registry.example.com/aqua-web:1.0.0
docker push registry.example.com/aqua-api:1.0.0
```

### Kubernetes Deployment

See `deployment/kubernetes/` folder for K8s manifests.

```bash
kubectl apply -f deployment/kubernetes/
```

### Environment Configuration

Create production `.env`:
```dotenv
MODEL_PATH=/models/model.onnx
API_KEY=<production-secret>
RATE_LIMIT_PER_MIN=1000
S3_BUCKET=prod-aqua-results
AWS_ACCESS_KEY_ID=<iam-key>
AWS_SECRET_ACCESS_KEY=<iam-secret>
AWS_REGION=us-east-1
```

## Security Checklist

- [ ] Set strong `API_KEY` for production
- [ ] Configure CORS for production domain
- [ ] Use HTTPS for all traffic
- [ ] Rotate AWS credentials regularly
- [ ] Enable S3 bucket encryption
- [ ] Set up API rate limiting
- [ ] Monitor logs for suspicious activity
- [ ] Keep Docker images updated
- [ ] Use secrets management (Vault, K8s Secrets)

---

For deployment to cloud platforms, see relevant documentation in `scripts/deploy.md`.
