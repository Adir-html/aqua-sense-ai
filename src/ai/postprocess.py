"""
Postprocessing for ONNX classification model.
Handles exactly 2 classes: ["normal", "faulty"]
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)


def softmax(x: np.ndarray) -> np.ndarray:
    """
    Convert logits to probabilities using softmax.
    
    Args:
        x: numpy array of logits
        
    Returns:
        numpy array of probabilities (same shape as input)
    """
    # Subtract max for numerical stability
    exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return exp_x / np.sum(exp_x, axis=-1, keepdims=True)


def postprocess_logits(logits: np.ndarray, classes: list) -> tuple:
    """
    Convert model logits → (predicted_label, confidence)

    Args:
        logits: numpy array of shape (1, 2) or (2,)
        classes: list of exactly 2 class names, e.g., ["normal", "faulty"]

    Returns:
        tuple: (predicted_label: str, confidence: float)
        
    Example:
        >>> logits = np.array([[2.1, -0.5]])
        >>> label, conf = postprocess_logits(logits, ["normal", "faulty"])
        >>> # Returns ("normal", 0.92)
    """
    try:
        # Remove batch dimension if present
        if logits.ndim > 1:
            logits = logits[0]
        
        logger.debug(f"🔍 Raw logits: {logits}")

        # Convert logits → probabilities
        probs = softmax(logits)
        logger.debug(f"   Probabilities: {probs}")

        # Pick class with highest probability
        idx = int(np.argmax(probs))
        if idx >= len(classes):
            logger.error(f"Model returned index {idx} but only {len(classes)} classes defined — defaulting to 0")
            idx = 0
        label = classes[idx]
        confidence = float(probs[idx])
        
        logger.debug(f"   Predicted: {label} (confidence: {confidence:.3f})")

        return label, confidence
        
    except Exception as e:
        logger.error(f"❌ Postprocessing failed: {e}")
        raise
