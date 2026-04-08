"""
AI inference runner — three-tier pipeline:

  1. OpenRouter (if OPENROUTER_API_KEY is set)         ← primary, Gemini 2.0 Flash
  2. ONNX MobileNetV2 (if MODEL_PATH model is loaded)  ← fast, offline fallback
  3. Brightness heuristic (always available)            ← last resort
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

_CLASSES    = ["faulty", "normal"]
_FAULTY_IDX = 0
_NORMAL_IDX  = 1


# ── Public entry point ────────────────────────────────────────────────────────

def run(image_path: str) -> Dict[str, Any]:
    """Analyze an image and return a structured result dict."""

    # Tier 1: OpenRouter (Gemini 2.0 Flash) — primary engine
    result = _try_openrouter(image_path)
    if result:
        return result

    # Tier 2: ONNX model — fast offline inference
    result = _try_onnx(image_path)
    if result:
        return result

    # Tier 3: Brightness heuristic — always works, least accurate
    logger.warning("All AI tiers unavailable — using brightness heuristic")
    return _fallback_heuristic(image_path)


# ── Tier 1: OpenRouter ───────────────────────────────────────────────────────

def _try_openrouter(image_path: str) -> Dict[str, Any] | None:
    try:
        from src.ai.openrouter_vision import analyze, is_available, QuotaExceededError
        if not is_available():
            logger.debug("OpenRouter not available (OPENROUTER_API_KEY not set)")
            return None

        logger.info("Using OpenRouter for analysis")
        return analyze(image_path)

    except Exception as e:
        from src.ai.openrouter_vision import QuotaExceededError
        if isinstance(e, QuotaExceededError):
            raise  # propagate quota errors — do not silently fall back
        logger.warning(f"OpenRouter failed ({e}) — falling back to next tier")
        return None


# ── Tier 2: ONNX model ────────────────────────────────────────────────────────

def _try_onnx(image_path: str) -> Dict[str, Any] | None:
    try:
        import numpy as np
        from src.ai.preprocess import preprocess
        from src.ai.postprocess import softmax
        from src.ai.inference_client import get_inference_client

        client = get_inference_client()
        if not client.is_ready():
            logger.debug("ONNX model not ready")
            return None

        logger.info(f"Using ONNX model for analysis: {image_path}")

        input_array = preprocess(image_path)
        logits      = client.predict(input_array)

        logits_1d   = logits[0] if logits.ndim > 1 else logits
        probs       = softmax(logits_1d)

        faulty_prob = float(probs[_FAULTY_IDX])
        normal_prob = float(probs[_NORMAL_IDX])

        idx        = int(np.argmax(probs))
        result     = _CLASSES[idx]
        confidence = float(probs[idx])

        logger.info(f"ONNX result: {result} (conf={confidence:.3f})")

        return {
            "result":             result,
            "confidence":         round(confidence, 4),
            "issue_detected":     result == "faulty",
            "message":            _onnx_message(result, confidence),
            "model_type":         "onnx_classification",
            "faulty_probability": round(faulty_prob, 4),
            "normal_probability": round(normal_prob, 4),
        }

    except Exception as e:
        logger.warning(f"ONNX inference failed ({e}) — falling back to heuristic")
        return None


def _onnx_message(result: str, confidence: float) -> str:
    pct = round(confidence * 100)
    if result == "faulty":
        if confidence >= 0.90:
            return f"High confidence ({pct}%): Irrigation issue detected. Inspect system immediately."
        elif confidence >= 0.70:
            return f"Moderate confidence ({pct}%): Probable fault detected. Schedule a system check."
        else:
            return f"Low confidence ({pct}%): Possible issue — manual inspection recommended."
    else:
        if confidence >= 0.90:
            return f"High confidence ({pct}%): Water system operating normally."
        elif confidence >= 0.70:
            return f"Moderate confidence ({pct}%): System appears normal. Continue routine monitoring."
        else:
            return f"Low confidence ({pct}%): System likely normal, but result is uncertain."


# ── Tier 3: Brightness heuristic ─────────────────────────────────────────────

def _fallback_heuristic(image_path: str) -> Dict[str, Any]:
    """Simple brightness + colour heuristic — last resort only."""
    try:
        from PIL import Image
        import numpy as np

        with Image.open(image_path) as img:
            arr    = np.array(img.convert("RGB").resize((128, 128)), dtype=np.float32)
            r_mean = float(arr[:, :, 0].mean())
            b_mean = float(arr[:, :, 2].mean())
            bright = float(arr.mean())

        turbidity_score = (r_mean - b_mean) / 255.0
        darkness_score  = max(0.0, (100.0 - bright) / 100.0)
        fault_score     = min(0.97, max(0.03, turbidity_score * 0.6 + darkness_score * 0.4))
        normal_score    = round(1.0 - fault_score, 4)
        fault_score     = round(fault_score, 4)

        if fault_score > 0.5:
            return {
                "result":             "faulty",
                "confidence":         fault_score,
                "issue_detected":     True,
                "message":            f"[Heuristic] Possible fault detected (turbidity={turbidity_score:.2f}, brightness={bright:.0f}).",
                "model_type":         "heuristic",
                "faulty_probability": fault_score,
                "normal_probability": normal_score,
            }
        else:
            return {
                "result":             "normal",
                "confidence":         normal_score,
                "issue_detected":     False,
                "message":            f"[Heuristic] No obvious fault detected (brightness={bright:.0f}).",
                "model_type":         "heuristic",
                "faulty_probability": fault_score,
                "normal_probability": normal_score,
            }

    except Exception:
        return {
            "result":             "unknown",
            "confidence":         0.0,
            "issue_detected":     False,
            "message":            "[Heuristic] Could not analyze image.",
            "model_type":         "none",
            "faulty_probability": 0.0,
            "normal_probability": 0.0,
        }
