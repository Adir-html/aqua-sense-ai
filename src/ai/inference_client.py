"""
Inference client for running ONNX model predictions.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class InferenceClient:
    """
    Loads an ONNX model and performs inference.
    Supports models with external data files (model.onnx + model.onnx.data).
    """

    def __init__(self, model_path=None):
        """
        Initialize the ONNX inference client.
        
        Args:
            model_path: Path to ONNX model file. If None, uses MODEL_PATH environment variable.
        """
        # Load model path from argument or environment
        self.model_path = model_path or os.environ.get("MODEL_PATH", "models/model.onnx")
        
        # Convert to absolute path if relative
        if not os.path.isabs(self.model_path):
            # Find workspace root by looking for a marker file (like models/ directory)
            current = Path(__file__).resolve()
            workspace_root = None
            
            # Go up until we find the workspace root (where models/ exists)
            for parent in current.parents:
                if (parent / "models").exists() and (parent / "models").is_dir():
                    workspace_root = parent
                    break
            
            if workspace_root is None:
                # Fallback: assume we're in src/ai/ and go up 2 levels
                workspace_root = Path(__file__).resolve().parents[2]
            
            self.model_path = str(workspace_root / self.model_path)
        
        self.session = None
        self._load_model()

    def _load_model(self):
        """
        Load ONNX model using onnxruntime.
        Handles models with external data files automatically.
        """
        try:
            model_file = Path(self.model_path)
            
            if not model_file.exists():
                logger.error(f"❌ Model file not found: {self.model_path}")
                logger.info(f"   Check that the model exists at this path")
                return

            # Check for external data file
            data_file = model_file.parent / f"{model_file.name}.data"
            if data_file.exists():
                logger.info(f"📦 Found external data file: {data_file.name}")

            import onnxruntime as ort

            # Create session options for better control
            sess_options = ort.SessionOptions()
            sess_options.log_severity_level = 3  # Error only (0=Verbose, 1=Info, 2=Warning, 3=Error, 4=Fatal)

            self.session = ort.InferenceSession(
                str(model_file),
                sess_options=sess_options,
                providers=["CPUExecutionProvider"]
            )

            # Log model details
            input_name = self.session.get_inputs()[0].name
            input_shape = self.session.get_inputs()[0].shape
            output_name = self.session.get_outputs()[0].name
            output_shape = self.session.get_outputs()[0].shape

            logger.info(f"✅ ONNX model loaded successfully!")
            logger.info(f"   Model path: {self.model_path}")
            logger.info(f"   Input: {input_name} {input_shape}")
            logger.info(f"   Output: {output_name} {output_shape}")

        except ImportError:
            logger.error("❌ onnxruntime not installed. Install with: pip install onnxruntime")
            self.session = None
        except Exception as e:
            logger.error(f"❌ Failed to load ONNX model: {e}")
            logger.exception("Full traceback:")
            self.session = None

    def is_ready(self):
        """
        Returns True if the ONNX model is loaded and ready for inference.
        """
        return self.session is not None

    def predict(self, input_array):
        """
        Run inference on a preprocessed numpy array.

        Args:
            input_array: numpy array of shape (1, 3, 224, 224), dtype float32

        Returns:
            numpy array of logits, shape (1, 2) for binary classification
        """
        if not self.is_ready():
            raise RuntimeError("Model is not loaded. Cannot perform inference.")

        try:
            # Get input name from the model
            input_name = self.session.get_inputs()[0].name
            
            # Run inference
            outputs = self.session.run(None, {input_name: input_array})
            
            # Return raw logits (first output)
            return outputs[0]

        except Exception as e:
            logger.error(f"❌ ONNX inference failed: {e}")
            logger.exception("Full traceback:")
            raise


# Global singleton instance
_global_client = None


def get_inference_client():
    """
    Returns a singleton inference client.
    Loads the model only once per application lifecycle.
    """
    global _global_client
    if _global_client is None:
        logger.info("🚀 Initializing global ONNX inference client...")
        _global_client = InferenceClient()
    return _global_client
