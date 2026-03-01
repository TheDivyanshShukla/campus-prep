import fitz # PyMuPDF
import cv2
import numpy as np
from PIL import Image
import os
import io
import pytesseract

def pdf_to_images(pdf_path):
    """
    Converts PDF pages to OpenCV/Numpy images.
    """
    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3)) # 3x zoom for high quality OCR (~450 DPI)
        img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        img = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR) if pix.n == 3 else img_data
        images.append(img)
    doc.close()
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

def images_to_pdf_ocr(images, output_path, dpi=300, tesseract_path=None):
    """
    Rebuilds a searchable PDF from a list of images using Tesseract OCR.
    """
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        
    pdf_writer = fitz.open()
    
    for idx, img in enumerate(images):
        if len(img.shape) == 3:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
        else:
            pil_img = Image.fromarray(img)
        
        # Perform OCR and get searchable PDF bytes for this page
        pdf_bytes = pytesseract.image_to_pdf_or_hocr(pil_img, extension='pdf')
        
        # Load the single-page PDF bytes and insert into main document
        with fitz.open("pdf", pdf_bytes) as page_pdf:
            pdf_writer.insert_pdf(page_pdf)
            
    pdf_writer.save(output_path)
    pdf_writer.close()
