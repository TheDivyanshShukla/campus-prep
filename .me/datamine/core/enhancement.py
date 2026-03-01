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
