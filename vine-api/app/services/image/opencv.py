"""OpenCV-based image analysis for wine bottle detection and quality assessment."""

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class BottleDetection:
    """Detected bottle bounding box."""

    bbox: Tuple[int, int, int, int]  # x, y, w, h
    confidence: float
    aspect_ratio: float


@dataclass
class OpenCVAnalysis:
    """Result of OpenCV image analysis."""

    single_bottle: bool = False
    multiple_bottles: bool = False
    upright: bool = False
    background_clean: bool = False
    sharpness_score: float = 0.0
    glare_score: float = 0.0
    label_visible: bool = False
    watermark_suspected: bool = False
    lifestyle_detected: bool = False
    opencv_pass: bool = False
    rejection_reason: Optional[str] = None
    bottle_bbox: Optional[Tuple[int, int, int, int]] = None


class OpenCVAnalyzer:
    """Analyze wine bottle images using OpenCV heuristics."""

    def analyze(self, image_path: str) -> OpenCVAnalysis:
        """Run full OpenCV analysis on an image."""
        if not image_path or not os.path.exists(image_path):
            return OpenCVAnalysis(
                opencv_pass=False,
                rejection_reason="No local image path or file missing",
            )

        img = cv2.imread(image_path)
        if img is None:
            return OpenCVAnalysis(
                opencv_pass=False,
                rejection_reason="Could not load image",
            )

        height, width = img.shape[:2]

        sharpness = self._calculate_sharpness(img)
        bottles = self._detect_bottles(img)
        single_bottle = len(bottles) == 1
        multiple_bottles = len(bottles) > 1
        upright = self._check_upright(bottles, width, height) if bottles else False
        background_clean = self._check_background(img, bottles)
        glare_score = self._calculate_glare(img)
        label_visible = self._check_label_visibility(img, bottles)
        watermark_suspected = self._detect_watermark(img)
        lifestyle_detected = self._detect_lifestyle(img, bottles)

        # Critical failures that hard-reject
        critical_fail = multiple_bottles or lifestyle_detected or sharpness < 30.0

        # Pass if not critically failed and single bottle with visible label
        opencv_pass = not critical_fail and single_bottle and label_visible

        warnings = []
        if not single_bottle and not multiple_bottles:
            warnings.append("No bottle detected")
        if not upright:
            warnings.append("Bottle not perfectly upright")
        if not background_clean:
            warnings.append("Background not clean")
        if sharpness < 50.0:
            warnings.append(f"Moderate blur (sharpness: {sharpness:.1f})")
        if glare_score >= 0.5:
            warnings.append(f"Some glare (score: {glare_score:.2f})")
        if watermark_suspected:
            warnings.append("Possible watermark")

        rejection_reason = "; ".join(warnings) if warnings else None

        bottle_bbox = bottles[0].bbox if bottles else None

        return OpenCVAnalysis(
            single_bottle=single_bottle,
            multiple_bottles=multiple_bottles,
            upright=upright,
            background_clean=background_clean,
            sharpness_score=sharpness / 100.0,
            glare_score=glare_score,
            label_visible=label_visible,
            watermark_suspected=watermark_suspected,
            lifestyle_detected=lifestyle_detected,
            opencv_pass=opencv_pass,
            rejection_reason=rejection_reason,
            bottle_bbox=bottle_bbox,
        )

    def _calculate_sharpness(self, img: np.ndarray) -> float:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return laplacian_var

    def _detect_bottles(self, img: np.ndarray) -> List[BottleDetection]:
        height, width = img.shape[:2]
        bottles = []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            total_area = width * height

            if area < total_area * 0.05:
                continue
            if area > total_area * 0.95:
                continue

            aspect_ratio = h / w if w > 0 else 0
            if aspect_ratio < 1.5 or aspect_ratio > 6.0:
                continue

            confidence = min(area / (total_area * 0.3), 1.0)
            bottles.append(
                BottleDetection(
                    bbox=(x, y, w, h),
                    confidence=confidence,
                    aspect_ratio=aspect_ratio,
                )
            )

        bottles.sort(key=lambda b: b.confidence, reverse=True)
        return bottles[:3]

    def _check_upright(
        self, bottles: List[BottleDetection], img_width: int, img_height: int
    ) -> bool:
        if not bottles:
            return False

        bottle = bottles[0]
        x, y, w, h = bottle.bbox

        center_x = x + w / 2
        center_y = y + h / 2
        img_center_x = img_width / 2
        img_center_y = img_height / 2

        x_deviation = abs(center_x - img_center_x) / img_width
        y_deviation = abs(center_y - img_center_y) / img_height

        upright = bottle.aspect_ratio > 2.5 and x_deviation < 0.3 and y_deviation < 0.3
        return upright

    def _check_background(
        self, img: np.ndarray, bottles: List[BottleDetection]
    ) -> bool:
        height, width = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if bottles:
            x, y, w, h = bottles[0].bbox
            mask = np.zeros((height, width), dtype=np.uint8)
            mask[y : y + h, x : x + w] = 255
            background = cv2.bitwise_and(gray, cv2.bitwise_not(mask))
        else:
            background = gray

        mean_bg = (
            np.mean(background[background > 0])
            if np.any(background > 0)
            else 128
        )
        std_bg = (
            np.std(background[background > 0])
            if np.any(background > 0)
            else 50
        )

        clean = std_bg < 60 and (mean_bg > 100 or mean_bg < 200)
        return clean

    def _calculate_glare(self, img: np.ndarray) -> float:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, bright_mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        bright_pixels = cv2.countNonZero(bright_mask)
        total_pixels = img.shape[0] * img.shape[1]
        return bright_pixels / total_pixels

    def _check_label_visibility(
        self, img: np.ndarray, bottles: List[BottleDetection]
    ) -> bool:
        if not bottles:
            return False

        height, width = img.shape[:2]
        x, y, w, h = bottles[0].bbox

        label_y_start = y + int(h * 0.25)
        label_y_end = y + int(h * 0.75)
        label_x_start = x + int(w * 0.15)
        label_x_end = x + int(w * 0.85)

        label_region = img[label_y_start:label_y_end, label_x_start:label_x_end]
        if label_region.size == 0:
            return False

        label_gray = cv2.cvtColor(label_region, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(label_gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        return edge_density > 0.01

    def _detect_watermark(self, img: np.ndarray) -> bool:
        height, width = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        h_lines = np.sum(edges, axis=0)
        v_lines = np.sum(edges, axis=1)

        h_peaks = np.sum(h_lines > np.mean(h_lines) * 3)
        v_peaks = np.sum(v_lines > np.mean(v_lines) * 3)

        if h_peaks > width * 0.1 or v_peaks > height * 0.1:
            return True

        corners = [
            gray[0 : int(height * 0.15), 0 : int(width * 0.15)],
            gray[0 : int(height * 0.15), int(width * 0.85) : width],
            gray[int(height * 0.85) : height, 0 : int(width * 0.15)],
            gray[int(height * 0.85) : height, int(width * 0.85) : width],
        ]

        corner_text_density = 0
        for corner in corners:
            if corner.size > 0:
                edges = cv2.Canny(corner, 50, 150)
                corner_text_density += (
                    np.sum(edges > 0) / edges.size if edges.size > 0 else 0
                )

        return corner_text_density > 0.05

    def _detect_lifestyle(
        self, img: np.ndarray, bottles: List[BottleDetection]
    ) -> bool:
        height, width = img.shape[:2]

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        skin_lower = np.array([0, 20, 70], dtype=np.uint8)
        skin_upper = np.array([20, 255, 255], dtype=np.uint8)
        skin_mask = cv2.inRange(hsv, skin_lower, skin_upper)

        skin_pixels = cv2.countNonZero(skin_mask)
        skin_ratio = skin_pixels / (height * width)

        if skin_ratio > 0.05:
            return True

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        bottle_mask = np.zeros((height, width), dtype=np.uint8)
        if bottles:
            for bottle in bottles:
                x, y, w, h = bottle.bbox
                bottle_mask[y : y + h, x : x + w] = 255

        background_edges = cv2.bitwise_and(edges, cv2.bitwise_not(bottle_mask))
        background_edge_density = np.sum(background_edges > 0) / (height * width)

        return background_edge_density > 0.15

    def get_bottle_bbox(self, image_path: str) -> Optional[Tuple[int, int, int, int]]:
        """Get the bounding box of the primary detected bottle."""
        if not image_path or not os.path.exists(image_path):
            return None

        img = cv2.imread(image_path)
        if img is None:
            return None

        bottles = self._detect_bottles(img)
        return bottles[0].bbox if bottles else None
