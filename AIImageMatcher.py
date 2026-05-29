"""
AIImageMatcher — semantic UI-element detection using ONNX Runtime.

This module wraps an ONNX model (e.g. YOLOv8-nano or a custom UI-detector)
to find on-screen elements by label instead of brittle template matching.

Usage:
    matcher = AIImageMatcher("path/to/model.onnx")
    results = matcher.find("settings icon")
    for r in results:
        print(r.label, r.bbox, r.confidence)

Installation:
    pip install onnxruntime opencv-python numpy
"""

import sys
from dataclasses import dataclass
from typing import List, Tuple, Optional

# Lazy imports — only load when first used to keep startup fast
_onnxruntime = None
_cv2 = None
_np = None


def _ensure_deps():
    global _onnxruntime, _cv2, _np
    if _onnxruntime is None:
        try:
            import onnxruntime as ort
            _onnxruntime = ort
        except ImportError:
            raise ImportError("onnxruntime is required. Run: pip install onnxruntime")
    if _cv2 is None:
        import cv2
        _cv2 = cv2
    if _np is None:
        import numpy as np
        _np = np


@dataclass
class MatchResult:
    label: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2


class AIImageMatcher:
    """ONNX-based semantic screen-element detector."""

    def __init__(self, model_path: Optional[str] = None):
        self.session = None
        self.input_name = None
        self.input_shape = None
        self.labels = []
        self._model_path = model_path
        self._initialized = False

    def _init(self):
        if self._initialized:
            return
        _ensure_deps()
        if self._model_path is None:
            # No model configured — fallback to template matching
            self._initialized = True
            return
        providers = _onnxruntime.get_available_providers()
        preferred = [p for p in ["DML", "CUDAExecutionProvider", "CPUExecutionProvider"] if p in providers]
        self.session = _onnxruntime.InferenceSession(self._model_path, providers=preferred or None)
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        # Attempt to load labels from adjacent .txt file
        label_path = self._model_path.replace(".onnx", "_labels.txt")
        try:
            with open(label_path, "r", encoding="utf-8") as f:
                self.labels = [line.strip() for line in f if line.strip()]
        except Exception:
            self.labels = []
        self._initialized = True

    def find(self, query: str, region=None, confidence: float = 0.5) -> List[MatchResult]:
        """
        Find all on-screen elements matching *query*.

        Parameters
        ----------
        query : str
            Semantic label to search for, e.g. "settings icon", "submit button".
        region : tuple | None
            Optional (x, y, w, h) bounding box to restrict search.
        confidence : float
            Minimum confidence threshold (0.0–1.0).

        Returns
        -------
        List[MatchResult]
            Detected elements sorted by confidence descending.
        """
        self._init()
        if self.session is None:
            # Fallback: no model loaded — return empty results so caller can use template matching
            return []

        # Capture screen region
        try:
            import pyautogui
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()
        except Exception:
            return []

        # Convert PIL → numpy BGR
        img = _np.array(screenshot)
        img = _cv2.cvtColor(img, _cv2.COLOR_RGB2BGR)
        h, w = img.shape[:2]

        # Pre-process (standard YOLOv8 letterbox)
        input_h = self.input_shape[2] if self.input_shape[2] is not None else 640
        input_w = self.input_shape[3] if self.input_shape[3] is not None else 640
        ratio = min(input_w / w, input_h / h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        pad_w = (input_w - new_w) % 32
        pad_h = (input_h - new_h) % 32
        resized = _cv2.resize(img, (new_w, new_h), interpolation=_cv2.INTER_LINEAR)
        padded = _np.full((input_h, input_w, 3), 114, dtype=_np.uint8)
        padded[:new_h, :new_w] = resized
        blob = padded.transpose(2, 0, 1)[None].astype(_np.float32) / 255.0

        # Inference
        outputs = self.session.run(None, {self.input_name: blob})
        preds = outputs[0][0]  # shape: (num_boxes, 4 + num_classes)

        # Post-process: NMS + filter by label
        boxes = []
        scores = []
        classes = []
        for det in preds.T:
            x_c, y_c, bw, bh, *cls_logits = det
            score = max(cls_logits)
            if score < confidence:
                continue
            cls_id = cls_logits.index(score)
            label = self.labels[cls_id] if cls_id < len(self.labels) else str(cls_id)
            if query.lower() not in label.lower():
                continue
            # Convert centre-size → xyxy
            x1 = int((x_c - bw / 2) / ratio)
            y1 = int((y_c - bh / 2) / ratio)
            x2 = int((x_c + bw / 2) / ratio)
            y2 = int((y_c + bh / 2) / ratio)
            if region:
                x1 += region[0]; y1 += region[1]
                x2 += region[0]; y2 += region[1]
            boxes.append([x1, y1, x2, y2])
            scores.append(score)
            classes.append(label)

        if not boxes:
            return []

        indices = _cv2.dnn.NMSBoxes(boxes, scores, confidence, 0.45)
        results = []
        for idx in indices.flatten():
            bbox = boxes[idx]
            results.append(MatchResult(label=classes[idx], confidence=scores[idx], bbox=tuple(bbox)))
        return sorted(results, key=lambda r: r.confidence, reverse=True)

    @staticmethod
    def is_available() -> bool:
        """Return True if onnxruntime is installed."""
        try:
            import onnxruntime
            return True
        except ImportError:
            return False
