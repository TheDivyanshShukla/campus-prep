import cv2
import numpy as np

def order_points(pts):
    """
    Orders 4 points in top-left, top-right, bottom-right, bottom-left order.
    """
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def four_point_transform(image, pts):
    """
    Applies a 4-point perspective transform to gain a top-down view of the document.
    """
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
    
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped

class DocumentPipeline:
    def __init__(self, config=None):
        self.config = config or {}

    def detect_page(self, image):
        """
        Detects the largest contour that looks like a page.
        """
        orig = image.copy()
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(gray, 75, 200)
        
        cnts = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if len(cnts) == 2 else cnts[1]
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]
        
        screenCnt = None
        img_area = image.shape[0] * image.shape[1]
        
        for c in cnts:
            area = cv2.contourArea(c)
            # Must be at least 15% of the image area to be considered a page
            if area < img_area * 0.15:
                continue
                
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4:
                screenCnt = approx
                break
        
        if screenCnt is not None:
            print(f"      - Document boundary detected (Area: {int(cv2.contourArea(screenCnt))}).")
            return four_point_transform(orig, screenCnt.reshape(4, 2))
        
        print("      - No significant document boundary detected. Using full image.")
        return orig

    def split_dual_page(self, image):
        """
        If the image is significantly wider than it is tall, split it down the middle.
        """
        h, w = image.shape[:2]
        if w > h * 1.2: # Typical threshold for dual page
            mid = w // 2
            left = image[:, :mid]
            right = image[:, mid:]
            return [left, right]
        return [image]

    def is_blank(self, image, threshold_low=0.002, threshold_high=0.9):
        """
        Detects if a page is essentially blank or invalid.
        Input should be a BW image (0=text, 255=background).
        """
        # Count black pixels (foreground)
        black_pixels = np.sum(image == 0)
        total_pixels = image.size
        ratio = black_pixels / total_pixels
        
        # A valid document page usually has 1% to 15% text coverage
        # If it's < 0.2% (blank) or > 90% (black/noise), it's invalid.
        return ratio < threshold_low or ratio > threshold_high

    def process_image(self, image):
        """
        Main entry point for processing an image page.
        """
        # 1. Detect and Crop Page
        image = self.detect_page(image)
        
        # 2. Split Dual Page if needed
        pages = self.split_dual_page(image)
        
        return pages
