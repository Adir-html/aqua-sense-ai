# Model Registry

This directory contains trained models for irrigation issue detection.

## Available Models

### TODO: Add trained models

- **model.onnx** (once trained) — Main ONNX model for production inference
  - Input: RGB image (1, 3, 224, 224)
  - Output: Classification logits for [no_issue, major_clog, leak]
  - Framework: PyTorch → ONNX
  - Status: Not yet created (train via `notebooks/train_model.ipynb`)

## Model Specifications

| Property | Value |
|----------|-------|
| Input Size | 224×224 RGB |
| Output Classes | 3 (no_issue, major_clog, leak) |
| Format | ONNX 1.12+ |
| Backend | ONNX Runtime |

## Loading a Model

```python
from src.ai.inference_client import InferenceClient

client = InferenceClient(model_path="models/model.onnx", framework="onnx")
result = client.predict(preprocessed_image)
```

Or set environment variables:
```bash
export MODEL_PATH=models/model.onnx
export MODEL_FRAMEWORK=onnx
```

## Training a New Model

See `notebooks/train_model.ipynb` for the complete training pipeline.

1. Prepare dataset in `dataset/normal/` and `dataset/faulty/`
2. Run the training notebook
3. Export to ONNX format
4. Save model.onnx here
