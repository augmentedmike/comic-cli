#!/usr/bin/env python3
"""
Comic Book Panel Splitter
Processes comic book images with multiple panels and splits them into individual images.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Optional
import logging

import cv2
import numpy as np
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class ComicPanelSplitter:
    """Main class for detecting and splitting comic book panels."""

    def __init__(self, min_panel_size: int = 5000, debug: bool = False):
        """
        Initialize the comic panel splitter.

        Args:
            min_panel_size: Minimum panel area in pixels to filter out noise
            debug: If True, save intermediate images for debugging
        """
        self.min_panel_size = min_panel_size
        self.debug = debug
        self.source_dir = Path("source")
        self.split_dir = Path("split")
        self.processed_dir = Path("processed")

        # Create output directories if they don't exist
        self.split_dir.mkdir(exist_ok=True)
        self.processed_dir.mkdir(exist_ok=True)

        # Statistics
        self.stats = {
            'images_processed': 0,
            'panels_detected': 0,
            'errors': 0
        }

    def detect_panels(self, image_path: Path) -> List[Tuple[int, int, int, int]]:
        """
        Detect individual panels in a comic book image.

        Args:
            image_path: Path to the comic book image

        Returns:
            List of panel bounding boxes as (x, y, width, height) tuples
        """
        logger.info(f"Detecting panels in {image_path.name}")

        # Load image
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            11,
            2
        )

        # Save debug images if requested
        if self.debug:
            debug_dir = Path("debug")
            debug_dir.mkdir(exist_ok=True)
            cv2.imwrite(str(debug_dir / f"{image_path.stem}_1_gray.jpg"), gray)
            cv2.imwrite(str(debug_dir / f"{image_path.stem}_2_thresh.jpg"), thresh)

        # Find contours
        contours, hierarchy = cv2.findContours(
            thresh,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        # Filter and process contours
        panels = []
        img_height, img_width = img.shape[:2]

        for contour in contours:
            # Approximate contour to polygon
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)

            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h

            # Filter by area and reasonable aspect ratio
            aspect_ratio = w / h if h > 0 else 0

            # Keep panels that:
            # - Are larger than minimum size
            # - Have reasonable aspect ratio (not too thin)
            # - Are not the entire image (with some tolerance)
            if (area >= self.min_panel_size and
                0.1 < aspect_ratio < 10 and
                w < img_width * 0.98 and h < img_height * 0.98):
                panels.append((x, y, w, h))

        # Sort panels by reading order (top-to-bottom, left-to-right)
        panels = self._sort_panels(panels, img_height)

        # Save debug image with detected panels
        if self.debug and panels:
            debug_img = img.copy()
            for i, (x, y, w, h) in enumerate(panels):
                cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 255, 0), 3)
                cv2.putText(debug_img, str(i + 1), (x + 10, y + 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            debug_dir = Path("debug")
            cv2.imwrite(str(debug_dir / f"{image_path.stem}_3_detected.jpg"), debug_img)

        logger.info(f"  Found {len(panels)} panels")
        return panels

    def _sort_panels(self, panels: List[Tuple[int, int, int, int]],
                     img_height: int) -> List[Tuple[int, int, int, int]]:
        """
        Sort panels by reading order (top-to-bottom, left-to-right).

        Args:
            panels: List of (x, y, w, h) tuples
            img_height: Height of the image

        Returns:
            Sorted list of panels
        """
        if not panels:
            return panels

        # Calculate average panel height for grouping tolerance
        avg_height = sum(h for _, _, _, h in panels) / len(panels)
        tolerance = avg_height * 0.3

        # Group panels by vertical position (rows)
        rows = []
        for panel in panels:
            x, y, w, h = panel
            placed = False

            for row in rows:
                row_y = row[0][1]  # y-coordinate of first panel in row
                if abs(y - row_y) < tolerance:
                    row.append(panel)
                    placed = True
                    break

            if not placed:
                rows.append([panel])

        # Sort panels within each row by x-coordinate (left-to-right)
        for row in rows:
            row.sort(key=lambda p: p[0])

        # Sort rows by y-coordinate (top-to-bottom)
        rows.sort(key=lambda row: row[0][1])

        # Flatten back to single list
        sorted_panels = [panel for row in rows for panel in row]
        return sorted_panels

    def extract_panels(self, image_path: Path, panels: List[Tuple[int, int, int, int]]) -> List[Path]:
        """
        Extract individual panels from the comic image and save them.

        Args:
            image_path: Path to the original comic image
            panels: List of panel bounding boxes

        Returns:
            List of paths to extracted panel images
        """
        if not panels:
            logger.warning(f"  No panels to extract from {image_path.name}")
            return []

        logger.info(f"Extracting {len(panels)} panels from {image_path.name}")

        # Load image using PIL to preserve quality and format
        img = Image.open(image_path)

        extracted_paths = []
        base_name = image_path.stem
        extension = image_path.suffix

        for i, (x, y, w, h) in enumerate(panels, 1):
            # Add small padding to avoid cutting off borders
            padding = 5
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(img.width, x + w + padding)
            y2 = min(img.height, y + h + padding)

            # Crop panel
            panel_img = img.crop((x1, y1, x2, y2))

            # Save with naming convention
            panel_filename = f"{base_name}_panel_{i:02d}{extension}"
            panel_path = self.split_dir / panel_filename

            # Preserve original quality
            panel_img.save(panel_path, quality=95)
            extracted_paths.append(panel_path)

            logger.info(f"  Saved panel {i}: {panel_filename}")

        return extracted_paths

    def enhance_image(self, image_path: Path, mode: str = 'none') -> Path:
        """
        Enhance image quality using various techniques.

        Args:
            image_path: Path to the image to enhance
            mode: Enhancement mode ('none', 'basic', or 'advanced')

        Returns:
            Path to the enhanced image
        """
        logger.info(f"Enhancing {image_path.name} (mode: {mode})")

        output_path = self.processed_dir / image_path.name

        if mode == 'none':
            # Just copy the file without modification - preserves original quality
            import shutil
            shutil.copy2(image_path, output_path)
            return output_path

        # Load image for processing
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")

        if mode == 'basic':
            # Gentle sharpening only (no brightness adjustment)
            kernel = np.array([[0, -1, 0],
                              [-1, 5, -1],
                              [0, -1, 0]])
            enhanced = cv2.filter2D(img, -1, kernel)

        elif mode == 'advanced':
            # Try to use Real-ESRGAN if available
            try:
                # This would require realesrgan package
                # For now, fall back to basic enhancement
                logger.warning("Advanced enhancement (Real-ESRGAN) not implemented yet, using basic mode")
                return self.enhance_image(image_path, mode='basic')
            except ImportError:
                logger.warning("Real-ESRGAN not available, using basic enhancement")
                return self.enhance_image(image_path, mode='basic')
        else:
            enhanced = img

        # Save enhanced image
        cv2.imwrite(str(output_path), enhanced, [cv2.IMWRITE_JPEG_QUALITY, 95])

        return output_path

    def process_pipeline(self, enhance_mode: str = 'none') -> dict:
        """
        Process all images in the source directory through the complete pipeline.

        Args:
            enhance_mode: Enhancement mode for processing

        Returns:
            Dictionary with processing statistics
        """
        logger.info("=" * 60)
        logger.info("Starting Comic Panel Splitting Pipeline")
        logger.info("=" * 60)

        # Find all image files in source directory
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        image_files = [
            f for f in self.source_dir.iterdir()
            if f.is_file() and f.suffix.lower() in image_extensions
        ]

        if not image_files:
            logger.warning(f"No image files found in {self.source_dir}")
            return self.stats

        logger.info(f"Found {len(image_files)} images to process\n")

        # Process each image
        for image_path in image_files:
            try:
                logger.info(f"Processing: {image_path.name}")

                # Step 1: Detect panels
                panels = self.detect_panels(image_path)
                self.stats['panels_detected'] += len(panels)

                # Step 2: Extract panels
                if panels:
                    extracted_paths = self.extract_panels(image_path, panels)

                    # Step 3: Enhance each extracted panel
                    for panel_path in extracted_paths:
                        self.enhance_image(panel_path, mode=enhance_mode)

                    self.stats['images_processed'] += 1
                else:
                    logger.warning(f"  No panels detected in {image_path.name}")

                logger.info("")  # Blank line for readability

            except Exception as e:
                logger.error(f"Error processing {image_path.name}: {e}")
                self.stats['errors'] += 1
                continue

        # Print summary
        self._print_summary()

        return self.stats

    def _print_summary(self):
        """Print processing summary statistics."""
        logger.info("=" * 60)
        logger.info("Processing Complete - Summary")
        logger.info("=" * 60)
        logger.info(f"Images processed: {self.stats['images_processed']}")
        logger.info(f"Total panels detected: {self.stats['panels_detected']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"\nOutput directories:")
        logger.info(f"  - Individual panels: {self.split_dir}/")
        logger.info(f"  - Enhanced images: {self.processed_dir}/")
        logger.info("=" * 60)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Split comic book images into individual panels',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python comic_splitter.py
  python comic_splitter.py --enhance-mode advanced
  python comic_splitter.py --debug --min-panel-size 10000
        """
    )

    parser.add_argument(
        '--enhance-mode',
        choices=['none', 'basic', 'advanced'],
        default='none',
        help='Enhancement quality mode: none=preserve original, basic=gentle sharpen, advanced=AI upscale (default: none)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Save intermediate images for debugging'
    )

    parser.add_argument(
        '--min-panel-size',
        type=int,
        default=5000,
        help='Minimum panel area in pixels (default: 5000)'
    )

    args = parser.parse_args()

    # Check if source directory exists
    source_dir = Path("source")
    if not source_dir.exists():
        logger.error(f"Source directory '{source_dir}' not found!")
        logger.error("Please create it and add comic book images to process.")
        sys.exit(1)

    # Create splitter instance and run pipeline
    splitter = ComicPanelSplitter(
        min_panel_size=args.min_panel_size,
        debug=args.debug
    )

    splitter.process_pipeline(enhance_mode=args.enhance_mode)


if __name__ == '__main__':
    main()
