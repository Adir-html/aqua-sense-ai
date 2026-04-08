"""
Preprocessing for ONNX MobileNetV2 model.
Matches PyTorch training transforms: resize 224x224, normalize ImageNet mean/std, CHW, batch.
"""

import numpy as np
from PIL import Image
from typing import Tuple, Union
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# ImageNet normalization constants (same as PyTorch default)
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def preprocess(image_path: Union[str, Path],
               input_size: Tuple[int, int] = (224, 224)) -> np.ndarray:
    """
    Load image → resize → normalize → CHW → batch.
    
    Matches standard MobileNetV2 preprocessing:
    1. Resize to 224x224
    2. Convert to float [0, 1]
    3. Normalize with ImageNet mean/std
    4. Convert to CHW format
    5. Add batch dimension
    
    Args:
        image_path: path to image file
        input_size: (height, width) tuple, default (224, 224)

    Returns:
        numpy array of shape (1, 3, 224, 224), dtype float32
    """
    try:
        # Load image
        img = Image.open(image_path).convert("RGB")
        logger.debug(f"📸 Loaded image: {image_path}, size: {img.size}")

        # Reject absurdly small or extremely large images
        w, h = img.size
        if w < 32 or h < 32:
            raise ValueError(f"Image too small ({w}x{h}) — minimum 32x32 pixels required")
        if w > 8000 or h > 8000:
            logger.warning(f"Very large image ({w}x{h}) — downsampling will be aggressive")

        # Resize to target size (width, height for PIL)
        img = img.resize((input_size[1], input_size[0]), Image.Resampling.BILINEAR)
        logger.debug(f"   Resized to: {input_size[1]}x{input_size[0]}")

        # Convert to numpy array: shape (H, W, C), values [0, 255]
        img_array = np.array(img, dtype=np.float32)
        
        # Scale to [0, 1]
        img_array = img_array / 255.0
        
        # Normalize using ImageNet mean and std
        # Broadcasting: (H, W, 3) - (3,) / (3,)
        img_array = (img_array - IMAGENET_MEAN) / IMAGENET_STD
        
        # Convert from HWC to CHW format
        img_array = np.transpose(img_array, (2, 0, 1))
        
        # Add batch dimension: (C, H, W) → (1, C, H, W)
        img_array = np.expand_dims(img_array, axis=0)
        
        logger.debug(f"   Preprocessed shape: {img_array.shape}, dtype: {img_array.dtype}")
        
        return img_array

    except Exception as e:
        logger.error(f"❌ Preprocessing failed for {image_path}: {e}")
        raise
