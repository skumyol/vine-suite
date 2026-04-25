"""Unified OCR preprocessing for all OCR engines."""

import io
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image


@dataclass
class PreprocessConfig:
    """Configuration for OCR preprocessing."""

    min_dimension: int = 200
    max_dimension: int = 4096
    target_height: int = 800  # Resize to this for consistent OCR
    denoise_strength: int = 10
    clahe_clip: float = 2.0
    clahe_grid: Tuple[int, int] = (8, 8)
    sharpen: bool = True
    unwrap_cylinder: bool = True
    binarize: bool = False


class OCRPreprocessor:
    """Preprocess images for optimal OCR across all engines."""

    def __init__(self, config: Optional[PreprocessConfig] = None):
        self.config = config or PreprocessConfig()

    def preprocess(self, image_bytes: bytes) -> bytes:
        """
        Full preprocessing pipeline:
        1. Load and validate
        2. Resize to target
        3. Unwrap cylindrical distortion
        4. Denoise
        5. Enhance contrast (CLAHE)
        6. Sharpen
        7. Optional binarize
        """
        img = self._load(image_bytes)
        if img is None:
            return image_bytes

        img = self._resize(img)
        if self.config.unwrap_cylinder:
            img = self._unwrap_cylinder(img)
        img = self._denoise(img)
        img = self._enhance_contrast(img)
        if self.config.sharpen:
            img = self._sharpen(img)
        if self.config.binarize:
            img = self._binarize(img)

        return self._to_bytes(img)

    def _load(self, image_bytes: bytes) -> Optional[np.ndarray]:
        """Load image from bytes."""
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception:
            return None

    def _to_bytes(self, img: np.ndarray) -> bytes:
        """Convert OpenCV image back to JPEG bytes."""
        _, encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return encoded.tobytes()

    def _resize(self, img: np.ndarray) -> np.ndarray:
        """Resize to target height while maintaining aspect ratio."""
        h, w = img.shape[:2]

        if h < self.config.min_dimension or w < self.config.min_dimension:
            return img  # Too small, skip

        if h > self.config.max_dimension or w > self.config.max_dimension:
            scale = self.config.max_dimension / max(h, w)
            w = int(w * scale)
            h = int(h * scale)
            img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)

        # Standardize height for OCR consistency
        if h != self.config.target_height:
            scale = self.config.target_height / h
            w = int(w * scale)
            h = self.config.target_height
            img = cv2.resize(img, (w, h), interpolation=cv2.INTER_LANCZOS4)

        return img

    def _unwrap_cylinder(self, img: np.ndarray) -> np.ndarray:
        """Reverse cylindrical distortion from bottle labels."""
        h, w = img.shape[:2]
        if w < h * 0.5:  # Already narrow / cropped
            return img

        # Detect label region
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return img

        # Find largest contour (assumed label boundary)
        largest = max(contours, key=cv2.contourArea)
        x, y, cw, ch = cv2.boundingRect(largest)

        # Only unwrap if contour is reasonable label-like region
        if cw < w * 0.3 or ch < h * 0.2:
            return img

        # Extract label region
        label_img = img[y : y + ch, x : x + cw]
        label_h, label_w = label_img.shape[:2]

        # Create destination for unwrapped label
        dst = np.zeros((label_h, label_w, 3), dtype=np.uint8)

        # Simple cylindrical unwrapping
        center_y = label_h // 2
        for row in range(label_h):
            # Map curved row to flat row with horizontal stretch compensation
            src_y = row
            for col in range(label_w):
                # Apply inverse cylindrical mapping
                # x' = r * arcsin(x/r) where r is cylinder radius
                # Approximate: linear interpolation with cosine weighting
                norm_x = (col / label_w - 0.5) * 2  # -1 to 1
                # Cosine correction for curvature
                correction = np.cos(norm_x * np.pi / 2)
                if correction > 0.1:
                    src_x = int((norm_x / correction + 1) / 2 * label_w)
                    src_x = max(0, min(label_w - 1, src_x))
                    if 0 <= src_x < label_w:
                        dst[row, col] = label_img[src_y, src_x]

        # Replace label region with unwrapped version
        img[y : y + ch, x : x + cw] = dst
        return img

    def _denoise(self, img: np.ndarray) -> np.ndarray:
        """Apply non-local means denoising."""
        return cv2.fastNlMeansDenoisingColored(
            img,
            None,
            h=self.config.denoise_strength,
            hColor=self.config.denoise_strength,
            templateWindowSize=7,
            searchWindowSize=21,
        )

    def _enhance_contrast(self, img: np.ndarray) -> np.ndarray:
        """Apply CLAHE in LAB color space."""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(
            clipLimit=self.config.clahe_clip,
            tileGridSize=self.config.clahe_grid,
        )
        l = clahe.apply(l)
        enhanced = cv2.merge([l, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    def _sharpen(self, img: np.ndarray) -> np.ndarray:
        """Unsharp mask sharpening."""
        gaussian = cv2.GaussianBlur(img, (0, 0), 3)
        return cv2.addWeighted(img, 1.5, gaussian, -0.5, 0)

    def _binarize(self, img: np.ndarray) -> np.ndarray:
        """Otsu thresholding for black-and-white text."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


# Global singleton instance
_default_preprocessor: Optional[OCRPreprocessor] = None


def get_preprocessor(config: Optional[PreprocessConfig] = None) -> OCRPreprocessor:
    """Get or create default preprocessor singleton."""
    global _default_preprocessor
    if _default_preprocessor is None:
        _default_preprocessor = OCRPreprocessor(config)
    return _default_preprocessor
