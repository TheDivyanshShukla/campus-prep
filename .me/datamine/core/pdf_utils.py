import fitz # PyMuPDF
import cv2
import numpy as np
from PIL import Image
import pytesseract


def _estimate_page_dpi(page, fallback_dpi=300):
    """
    Estimate the effective scan DPI from the largest embedded image on a page.
    Falls back to fallback_dpi when metadata is unavailable.
    """
    page_images = page.get_images(full=True)
    if not page_images:
        return fallback_dpi

    largest = max(page_images, key=lambda item: item[2] * item[3])
    img_w = largest[2]
    img_h = largest[3]

    page_w_in = page.rect.width / 72.0
    page_h_in = page.rect.height / 72.0
    if page_w_in <= 0 or page_h_in <= 0:
        return fallback_dpi

    dpi_x = img_w / page_w_in
    dpi_y = img_h / page_h_in
    estimated = int(round((dpi_x + dpi_y) / 2.0))
    return max(72, min(1200, estimated))


def _extract_largest_embedded_image(doc, page):
    """
    Extract the largest embedded raster image from a PDF page without re-rendering.
    Returns OpenCV BGR image or None.
    """
    page_images = page.get_images(full=True)
    if not page_images:
        return None

    largest = max(page_images, key=lambda item: item[2] * item[3])
    xref = largest[0]
    extracted = doc.extract_image(xref)
    if not extracted or "image" not in extracted:
        return None

    image_bytes = extracted["image"]
    decoded = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if decoded is None:
        return None

    if len(decoded.shape) == 2:
        decoded = cv2.cvtColor(decoded, cv2.COLOR_GRAY2BGR)

    if len(decoded.shape) == 3 and decoded.shape[2] == 4:
        decoded = cv2.cvtColor(decoded, cv2.COLOR_BGRA2BGR)

    return decoded


def _extract_significant_embedded_images(doc, page, min_area_ratio=0.12):
    """
    Extract significant page images with their own effective DPI and horizontal position.
    Returns list of tuples: (x0, image, image_dpi)
    """
    page_w = page.rect.width
    page_h = page.rect.height
    page_area = page_w * page_h if page_w > 0 and page_h > 0 else 0
    if page_area <= 0:
        return []

    collected = []
    for item in page.get_images(full=True):
        xref = item[0]
        img_w = item[2]
        img_h = item[3]
        rects = page.get_image_rects(xref)
        if not rects:
            continue

        rect = rects[0]
        rect_w = max(1e-6, rect.width)
        rect_h = max(1e-6, rect.height)
        area_ratio = (rect_w * rect_h) / page_area
        if area_ratio < min_area_ratio:
            continue

        extracted = doc.extract_image(xref)
        if not extracted or "image" not in extracted:
            continue

        decoded = cv2.imdecode(np.frombuffer(extracted["image"], dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if decoded is None:
            continue

        if len(decoded.shape) == 2:
            decoded = cv2.cvtColor(decoded, cv2.COLOR_GRAY2BGR)
        elif len(decoded.shape) == 3 and decoded.shape[2] == 4:
            decoded = cv2.cvtColor(decoded, cv2.COLOR_BGRA2BGR)

        dpi_x = img_w / (rect_w / 72.0)
        dpi_y = img_h / (rect_h / 72.0)
        img_dpi = int(round((dpi_x + dpi_y) / 2.0))
        img_dpi = max(72, min(1200, img_dpi))

        collected.append((rect.x0, decoded, img_dpi))

    collected.sort(key=lambda item: item[0])
    return collected


def pdf_to_images(pdf_path, dpi=300, preserve_source_dpi=True, return_dpi=False):
    """
    Converts PDF pages to OpenCV/Numpy images.
    """
    doc = fitz.open(pdf_path)
    images = []
    page_dpis = []
    for page in doc:
        if preserve_source_dpi:
            page_dpi = _estimate_page_dpi(page, fallback_dpi=dpi)
        else:
            page_dpi = dpi

        if preserve_source_dpi:
            significant = _extract_significant_embedded_images(doc, page)
            if significant:
                for _, extracted_img, extracted_dpi in significant:
                    images.append(extracted_img)
                    page_dpis.append(extracted_dpi)
                continue

        img = _extract_largest_embedded_image(doc, page) if preserve_source_dpi else None
        if img is None:
            pix = page.get_pixmap(dpi=page_dpi)
            img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
            img = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR) if pix.n == 3 else img_data

        images.append(img)
        page_dpis.append(page_dpi)
    doc.close()
    if return_dpi:
        return images, page_dpis
    return images

def images_to_pdf(images, output_path, dpi=300):
    """
    Rebuilds a standard PDF from a list of images.
    """
    pil_images = []
    for img in images:
        if len(img.shape) == 3:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
        else:
            pil_img = Image.fromarray(img)
        pil_images.append(pil_img)
    
    if pil_images:
        pil_images[0].save(output_path, "PDF", resolution=dpi, save_all=True, append_images=pil_images[1:])


def _save_pdf_with_optional_linearize(pdf_writer, output_path, linearize=True):
    try:
        pdf_writer.save(output_path, linear=linearize)
    except Exception as exc:
        if linearize and "Linearisation is no longer supported" in str(exc):
            pdf_writer.save(output_path)
        else:
            raise


def _add_hidden_ocr_text_layer(page, img, page_dpi, ocr_lang):
    if len(img.shape) == 3:
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
    else:
        pil_img = Image.fromarray(img)

    tesseract_config = f"--dpi {int(page_dpi)} -c textonly_pdf=1"
    text_pdf_bytes = pytesseract.image_to_pdf_or_hocr(
        pil_img,
        extension='pdf',
        lang=ocr_lang,
        config=tesseract_config,
    )

    with fitz.open("pdf", text_pdf_bytes) as text_pdf:
        page.show_pdf_page(page.rect, text_pdf, 0, overlay=True)


def _images_to_pdf_ocr_lossless(
    images,
    output_path,
    dpi=300,
    page_dpis=None,
    linearize=True,
    ocr_lang='eng',
):
    pdf_writer = fitz.open()
    for idx, img in enumerate(images):
        page_dpi = page_dpis[idx] if page_dpis and idx < len(page_dpis) else dpi
        h, w = img.shape[:2]
        page_width_pt = w * 72.0 / float(page_dpi)
        page_height_pt = h * 72.0 / float(page_dpi)

        ok, encoded = cv2.imencode('.png', img)
        if not ok:
            raise RuntimeError(f"Failed to encode page {idx + 1} as PNG.")

        page = pdf_writer.new_page(width=page_width_pt, height=page_height_pt)
        page.insert_image(page.rect, stream=encoded.tobytes())
        _add_hidden_ocr_text_layer(page, img, page_dpi, ocr_lang)

    _save_pdf_with_optional_linearize(pdf_writer, output_path, linearize=linearize)
    pdf_writer.close()

def images_to_pdf_ocr(
    images,
    output_path,
    dpi=300,
    tesseract_path=None,
    page_dpis=None,
    linearize=True,
    ocr_lang='eng',
    ocr_mode='lossless',
):
    """
    Rebuilds a searchable PDF from a list of images using Tesseract OCR.
    """
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

    if ocr_mode == 'lossless':
        _images_to_pdf_ocr_lossless(
            images,
            output_path,
            dpi=dpi,
            page_dpis=page_dpis,
            linearize=linearize,
            ocr_lang=ocr_lang,
        )
        return
        
    pdf_writer = fitz.open()
    
    for idx, img in enumerate(images):
        page_dpi = page_dpis[idx] if page_dpis and idx < len(page_dpis) else dpi
        if len(img.shape) == 3:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
        else:
            pil_img = Image.fromarray(img)
        
        # Perform OCR and get searchable PDF bytes for this page
        tesseract_config = f"--dpi {int(page_dpi)}"
        pdf_bytes = pytesseract.image_to_pdf_or_hocr(
            pil_img,
            extension='pdf',
            lang=ocr_lang,
            config=tesseract_config
        )
        
        # Load the single-page PDF bytes and insert into main document
        with fitz.open("pdf", pdf_bytes) as page_pdf:
            pdf_writer.insert_pdf(page_pdf)
            
    _save_pdf_with_optional_linearize(pdf_writer, output_path, linearize=linearize)
    pdf_writer.close()
