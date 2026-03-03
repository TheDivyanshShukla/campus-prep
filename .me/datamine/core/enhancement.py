import cv2
import numpy as np

def remove_shadows(image):
    """
    Illumination normalization or shadow removal.
    """
    rgb_planes = cv2.split(image)
    result_planes = []
    for plane in rgb_planes:
        dilated_img = cv2.dilate(plane, np.ones((7,7), np.uint8))
        bg_img = cv2.medianBlur(dilated_img, 21)
        diff_img = 255 - cv2.absdiff(plane, bg_img)
        norm_img = cv2.normalize(diff_img, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
        result_planes.append(norm_img)
    return cv2.merge(result_planes)

def enhance_scan(image, mode='color'):
    """
    Apply enhancements based on mode: color, grayscale, or bw.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
        
    # 1. Quality Improvement: Auto-invert if text is white on black background
    if np.mean(gray) < 100:
        gray = 255 - gray
        
    # 2. Contrast improvement using CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)

    if mode == 'grayscale':
        return gray
    elif mode == 'bw':
        # Safety: If page is already very white, don't over-process
        if np.mean(gray) > 240:
             # Just a simple threshold if already clean
             _, bw = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
             return bw

        # Adaptive threshold with larger block size for better text extraction
        bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 21, 10)
        
        # Final check: If result is > 99.5% white, it probably failed
        white_ratio = np.sum(bw == 255) / bw.size
        if white_ratio > 0.995:
            _, bw_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return bw_otsu
            
        return bw
    else: # mode == 'color'
        # Keep color but use the enhanced grayscale for contrast guidance if needed
        # For now, just sharpen the color original
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        return cv2.filter2D(image, -1, kernel)

def crop_fixed_percentage(image, percent_bottom=0):
    """
    Remove fixed percentage from bottom (e.g., footer removal).
    """
    if percent_bottom <= 0:
        return image
    h, w = image.shape[:2]
    crop_h = int(h * (1 - percent_bottom/100))
    return image[:crop_h, :]


def remove_large_black_blobs_by_font_size(
    image,
    padding=2,
    area_multiplier=1.0,
    density_threshold=0.45,
    edge_margin_px=6,
    edge_area_multiplier=0.35,
    edge_density_threshold=0.08,
):
    """
    Remove dark blobs larger than estimated largest text size.
    Includes an edge-artifact path for large border-touching blobs that may be
    less dense (e.g., black wedges near page corners).
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    _, binary_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary_inv, connectivity=8)

    text_heights = []
    for label_idx in range(1, num_labels):
        x = stats[label_idx, cv2.CC_STAT_LEFT]
        y = stats[label_idx, cv2.CC_STAT_TOP]
        w = stats[label_idx, cv2.CC_STAT_WIDTH]
        h = stats[label_idx, cv2.CC_STAT_HEIGHT]
        area = stats[label_idx, cv2.CC_STAT_AREA]
        if w <= 0 or h <= 0:
            continue

        aspect_ratio = w / float(h)
        if 4 <= area <= 1500 and 0.08 <= aspect_ratio <= 8.0 and 4 <= h <= 80:
            text_heights.append(h)

    if text_heights:
        largest_font_size = float(np.percentile(text_heights, 95))
    else:
        largest_font_size = 20.0

    area_threshold = max(20.0, area_multiplier * (largest_font_size ** 2))
    edge_area_threshold = max(20.0, edge_area_multiplier * area_threshold)

    cleaned = image.copy()
    page_h, page_w = gray.shape[:2]

    for label_idx in range(1, num_labels):
        x = stats[label_idx, cv2.CC_STAT_LEFT]
        y = stats[label_idx, cv2.CC_STAT_TOP]
        w = stats[label_idx, cv2.CC_STAT_WIDTH]
        h = stats[label_idx, cv2.CC_STAT_HEIGHT]
        area = float(stats[label_idx, cv2.CC_STAT_AREA])
        if w <= 0 or h <= 0:
            continue

        bbox_area = float(w * h)
        density = area / bbox_area if bbox_area > 0 else 0.0
        touches_edge = (
            x <= edge_margin_px
            or y <= edge_margin_px
            or (x + w) >= (page_w - edge_margin_px)
            or (y + h) >= (page_h - edge_margin_px)
        )

        standard_blob = area >= area_threshold and density >= density_threshold
        edge_blob = touches_edge and area >= edge_area_threshold and density >= edge_density_threshold

        if standard_blob or edge_blob:
            x0 = max(0, x - padding)
            y0 = max(0, y - padding)
            x1 = min(page_w, x + w + padding)
            y1 = min(page_h, y + h + padding)

            if len(cleaned.shape) == 3:
                cleaned[y0:y1, x0:x1] = (255, 255, 255)
            else:
                cleaned[y0:y1, x0:x1] = 255

    return cleaned


def remove_footer_link_area(
    image,
    box_width_ratio=0.62,
    box_height_ratio=0.075,
    bottom_margin_ratio=0.0,
):
    """
    Whiten a bottom-center box to remove URL/footer text artifacts.
    Ratios are relative to page width/height.
    """
    cleaned = image.copy()
    h, w = cleaned.shape[:2]

    box_w = max(1, int(w * box_width_ratio))*2
    box_h = max(1, int(h * box_height_ratio))
    margin = max(0, int(h * bottom_margin_ratio))

    x0 = max(0, (w - box_w) // 2)
    x1 = min(w, x0 + box_w)
    y1 = max(0, h - margin)
    y0 = max(0, y1 - box_h)

    if len(cleaned.shape) == 3:
        cleaned[y0:y1, x0:x1] = (255, 255, 255)
    else:
        cleaned[y0:y1, x0:x1] = 255

    return cleaned

