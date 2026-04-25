"""Label and neck region cropping for wine bottle images."""

import os
from typing import Dict, Optional, Tuple

import cv2
import numpy as np


class LabelCropper:
    """Extract bottle, label, and neck regions from wine bottle images."""

    def __init__(self, crops_dir: Optional[str] = None):
        self.crops_dir = crops_dir or os.path.join(os.getcwd(), "image_cache", "crops")
        os.makedirs(self.crops_dir, exist_ok=True)

    def extract_crops(
        self,
        image_path: str,
        bottle_bbox: Optional[Tuple[int, int, int, int]] = None,
    ) -> Dict[str, Optional[str]]:
        """
        Extract bottle, label, and neck crops from an image.

        Returns dict with keys: full, label, neck (paths or None)
        """
        if not image_path or not os.path.exists(image_path):
            return {"full": None, "label": None, "neck": None}

        img = cv2.imread(image_path)
        if img is None:
            return {"full": None, "label": None, "neck": None}

        base_name = os.path.splitext(os.path.basename(image_path))[0]

        if bottle_bbox:
            x, y, w, h = bottle_bbox
            bottle_crop = img[y : y + h, x : x + w]
        else:
            bottle_crop = img.copy()
            x, y, w, h = 0, 0, img.shape[1], img.shape[0]

        bottle_path = os.path.join(self.crops_dir, f"{base_name}_bottle.jpg")
        cv2.imwrite(bottle_path, bottle_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])

        label_bbox = self._detect_label_region(bottle_crop)
        if label_bbox:
            lx, ly, lw, lh = label_bbox
            label_crop = bottle_crop[ly : ly + lh, lx : lx + lw]
            label_path = os.path.join(self.crops_dir, f"{base_name}_label.jpg")
            cv2.imwrite(label_path, label_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
        else:
            label_path = None

        neck_bbox = self._detect_neck_region(bottle_crop)
        if neck_bbox:
            nx, ny, nw, nh = neck_bbox
            neck_crop = bottle_crop[ny : ny + nh, nx : nx + nw]
            neck_path = os.path.join(self.crops_dir, f"{base_name}_neck.jpg")
            cv2.imwrite(neck_path, neck_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
        else:
            neck_path = None

        return {"full": bottle_path, "label": label_path, "neck": neck_path}

    def _detect_label_region(
        self, bottle_img: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        """Detect the label region within a bottle crop."""
        height, width = bottle_img.shape[:2]
        gray = cv2.cvtColor(bottle_img, cv2.COLOR_BGR2GRAY)

        label_y_start = int(height * 0.25)
        label_y_end = int(height * 0.70)
        label_x_start = int(width * 0.10)
        label_x_end = int(width * 0.90)

        label_region = gray[label_y_start:label_y_end, label_x_start:label_x_end]

        # Threshold + edge detection for label boundary
        _, binary = cv2.threshold(
            label_region, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        edges = cv2.Canny(label_region, 50, 150)

        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            # Fallback: use default label region
            return (
                label_x_start + int(label_region.shape[1] * 0.1),
                label_y_start + int(label_region.shape[0] * 0.1),
                int(label_region.shape[1] * 0.8),
                int(label_region.shape[0] * 0.5),
            )

        best_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(best_contour)

        min_label_width = width * 0.3
        min_label_height = height * 0.1
        max_label_width = width * 0.9
        max_label_height = height * 0.5

        # Enforce minimum dimensions
        if w < min_label_width or h < min_label_height:
            x = int(label_region.shape[1] * 0.1)
            y = int(label_region.shape[0] * 0.1)
            w = int(label_region.shape[1] * 0.8)
            h = int(label_region.shape[0] * 0.5)

        # Clamp max dimensions
        if w > max_label_width:
            w = int(max_label_width)
        if h > max_label_height:
            h = int(max_label_height)

        absolute_x = label_x_start + x
        absolute_y = label_y_start + y

        return (absolute_x, absolute_y, w, h)

    def _detect_neck_region(
        self, bottle_img: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        """Detect the neck/foil region of a bottle."""
        height, width = bottle_img.shape[:2]

        neck_y_start = int(height * 0.05)
        neck_y_end = int(height * 0.25)
        neck_x_start = int(width * 0.25)
        neck_x_end = int(width * 0.75)

        if neck_y_end <= neck_y_start:
            return None

        return (
            neck_x_start,
            neck_y_start,
            neck_x_end - neck_x_start,
            neck_y_end - neck_y_start,
        )

    def enhance_for_ocr(self, image_path: str) -> str:
        """Enhance an image for better OCR results."""
        if not os.path.exists(image_path):
            return image_path

        img = cv2.imread(image_path)
        if img is None:
            return image_path

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

        # CLAHE contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        base_name = os.path.splitext(os.path.basename(image_path))[0]
        enhanced_path = os.path.join(self.crops_dir, f"{base_name}_enhanced.jpg")
        cv2.imwrite(enhanced_path, enhanced, [cv2.IMWRITE_JPEG_QUALITY, 95])

        return enhanced_path
