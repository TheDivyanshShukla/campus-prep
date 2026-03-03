import os
import argparse
import cv2
import json
from concurrent.futures import ProcessPoolExecutor
from core.pipeline import DocumentPipeline
from core.enhancement import (
    remove_shadows,
    enhance_scan,
    crop_fixed_percentage,
    remove_large_black_blobs_by_font_size,
    remove_footer_link_area,
)
from core.pdf_utils import pdf_to_images, images_to_pdf, images_to_pdf_ocr

class ScanProcessorCLI:
    def __init__(self, args):
        self.args = args
        self.pipeline = DocumentPipeline()
        # Auto-detect common Tesseract path on Windows
        if not self.args.tesseract_path:
            common_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(common_path):
                self.args.tesseract_path = common_path
        
    def process_single_file(self, file_path, output_folder):
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        
        print(f"[*] Processing {filename}...")
        
        # 1. Load Images
        if ext == '.pdf':
            images, source_page_dpis = pdf_to_images(
                file_path,
                dpi=self.args.dpi,
                preserve_source_dpi=self.args.preserve_source_dpi,
                return_dpi=True
            )
        else:
            img = cv2.imread(file_path)
            if img is None:
                print(f"[!] Error reading {filename}")
                return
            images = [img]
            source_page_dpis = [self.args.dpi]
            
        processed_pages = []
        processed_page_dpis = []
        for idx, img in enumerate(images):
            source_dpi = source_page_dpis[idx] if idx < len(source_page_dpis) else self.args.dpi
            # 2. Page Detection & Transform
            rect_pages = self.pipeline.process_image(img)
            
            if len(rect_pages) > 1:
                print(f"    - Page {idx+1}: Split into {len(rect_pages)} dual pages.")
            
            for p_idx, p in enumerate(rect_pages):
                # 3. Shadow Removal
                if not self.args.no_enhance:
                    p = remove_shadows(p)
                
                # 4. Mode Enhancement
                if not self.args.no_enhance:
                    p = enhance_scan(p, mode=self.args.mode)
                
                # 5. Skip if blank (using BW version for detection)
                if self.args.mode == 'bw' and not self.args.no_enhance:
                    bw_for_check = p
                else:
                    # Convert to grayscale first if it's 3-channel
                    gray_for_check = p
                    if len(p.shape) == 3:
                        gray_for_check = cv2.cvtColor(p, cv2.COLOR_BGR2GRAY)
                    _, bw_for_check = cv2.threshold(gray_for_check, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                if self.pipeline.is_blank(bw_for_check):
                    print(f"    - Page {idx+1}.{p_idx+1}: Blank page detected. Skipping.")
                    continue

                if self.args.remove_black_blobs:
                    p = remove_large_black_blobs_by_font_size(
                        p,
                        padding=self.args.black_blob_padding,
                        area_multiplier=self.args.black_blob_area_multiplier,
                        density_threshold=self.args.black_blob_density_threshold,
                    )

                if self.args.remove_footer_link:
                    p = remove_footer_link_area(
                        p,
                        box_width_ratio=self.args.footer_link_box_width_ratio,
                        box_height_ratio=self.args.footer_link_box_height_ratio,
                        bottom_margin_ratio=self.args.footer_link_bottom_margin_ratio,
                    )


                # 6. Bottom Crop (Footer Removal)
                if self.args.remove_footer > 0:
                    p = crop_fixed_percentage(p, self.args.remove_footer)
                    
                processed_pages.append(p)
                processed_page_dpis.append(source_dpi)
        
        # 6. Save Output
        if not processed_pages:
            return

        base_name = os.path.splitext(filename)[0]
        output_pdf_path = os.path.join(output_folder, f"{base_name}.pdf")
        if self.args.ocr:
            images_to_pdf_ocr(
                processed_pages,
                output_pdf_path,
                dpi=self.args.dpi,
                tesseract_path=self.args.tesseract_path,
                page_dpis=processed_page_dpis,
                linearize=self.args.linearize,
                ocr_lang=self.args.ocr_lang,
                ocr_mode=self.args.ocr_mode,
                ocr_psm=self.args.ocr_psm,
                ocr_border_clean_px=self.args.ocr_border_clean_px,
            )
        else:
            images_to_pdf(processed_pages, output_pdf_path, dpi=self.args.dpi)
        
        if self.args.save_images:
            img_folder = os.path.join(output_folder, base_name)
            os.makedirs(img_folder, exist_ok=True)
            for i, p in enumerate(processed_pages):
                cv2.imwrite(os.path.join(img_folder, f"page_{i+1}.png"), p)
        
        print(f"[+] Finished {filename}")

def run_job(args_tuple):
    file_path, output_folder, args = args_tuple
    try:
        processor = ScanProcessorCLI(args)
        processor.process_single_file(file_path, output_folder)
    except Exception as exc:
        print(f"[!] Failed processing {os.path.basename(file_path)}: {exc}")

def main():
    parser = argparse.ArgumentParser(description="ScanProcess: Automated Document Scan Cleanup")
    parser.add_argument("input", nargs="?", default="samples", help="Input folder containing images or PDFs (default: samples)")
    parser.add_argument("output", nargs="?", default="output_scans", help="Output folder for processed results (default: output_scans)")
    parser.add_argument("--mode", choices=['color', 'grayscale', 'bw'], default='color', help="Scan mode")
    parser.add_argument("--dpi", type=int, default=300, help="Output DPI")
    parser.add_argument("--preserve-source-dpi", dest="preserve_source_dpi", action="store_true", help="Estimate and preserve source page DPI for PDF inputs")
    parser.add_argument("--no-preserve-source-dpi", dest="preserve_source_dpi", action="store_false", help="Disable source DPI estimation and force --dpi")
    parser.add_argument("--ocr-lang", default="eng", help="Tesseract OCR language(s), e.g. 'eng' or 'eng+hin'")
    parser.add_argument("--ocr-mode", choices=["lossless", "tesseract-pdf"], default="lossless", help="OCR output mode")
    parser.add_argument("--ocr-psm", type=int, default=11, help="Tesseract page segmentation mode for OCR")
    parser.add_argument("--ocr-border-clean-px", type=int, default=10, help="Pixels to whiten on all borders for OCR-only preprocessing")
    parser.add_argument("--remove-footer", type=float, default=0, help="Percentage to crop from bottom")
    parser.add_argument("--remove-black-blobs", dest="remove_black_blobs", action="store_true", help="Remove dense black blobs larger than text size")
    parser.add_argument("--no-remove-black-blobs", dest="remove_black_blobs", action="store_false", help="Disable dense black blob cleanup")
    parser.add_argument("--black-blob-padding", type=int, default=2, help="Padding in pixels when whitening large black blobs")
    parser.add_argument("--black-blob-area-multiplier", type=float, default=1.0, help="Area threshold multiplier relative to largest font size squared")
    parser.add_argument("--black-blob-density-threshold", type=float, default=0.45, help="Minimum fill density for large black blob detection")
    parser.add_argument("--remove-footer-link", dest="remove_footer_link", action="store_true", help="Remove bottom-center footer link area")
    parser.add_argument("--no-remove-footer-link", dest="remove_footer_link", action="store_false", help="Keep original footer link area")
    parser.add_argument("--footer-link-box-width-ratio", type=float, default=0.62, help="Footer cleanup box width as ratio of page width")
    parser.add_argument("--footer-link-box-height-ratio", type=float, default=0.075, help="Footer cleanup box height as ratio of page height")
    parser.add_argument("--footer-link-bottom-margin-ratio", type=float, default=0.0, help="Footer cleanup bottom margin ratio")
    parser.add_argument("--watermark-text", default="rgpv.online.com", help="Watermark text to add on every page")
    parser.add_argument("--watermark-opacity", type=float, default=0.26, help="Watermark opacity (0.0 to 1.0)")
    parser.add_argument("--watermark-font-scale", type=float, default=1.0, help="Watermark font scale")
    parser.add_argument("--watermark-thickness", type=int, default=2, help="Watermark text thickness")
    parser.add_argument("--watermark-bottom-margin-px", type=int, default=12, help="Watermark bottom margin in pixels")
    parser.add_argument("--save-images", action="store_true", help="Save individual processed images")
    parser.add_argument("--linearize", dest="linearize", action="store_true", help="Save output PDF as linearized (fast web view)")
    parser.add_argument("--no-linearize", dest="linearize", action="store_false", help="Disable linearized PDF output")
    ocr_group = parser.add_mutually_exclusive_group()
    ocr_group.add_argument("--ocr", dest="ocr", action="store_true", help="Make PDF searchable (selectable text) using Tesseract")
    ocr_group.add_argument("--no-ocr", dest="ocr", action="store_false", help="Disable OCR output")
    parser.add_argument("--no-enhance", action="store_true", help="Skip aggressive enhancement (shadow removal/thresholding) to preserve original quality")
    parser.add_argument("--tesseract-path", help="Path to tesseract executable (e.g. C:\\Program Files\\Tesseract-OCR\\tesseract.exe)")
    parser.add_argument("--config", help="Path to JSON config file")
    
    parser.set_defaults(
        ocr=True,
        preserve_source_dpi=True,
        linearize=True,
        remove_black_blobs=True,
        remove_footer_link=True,
    )
    args = parser.parse_args()
    
    # Load config if provided
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r') as f:
            config = json.load(f)
            for k, v in config.items():
                setattr(args, k, v)
    
    # If using defaults that don't exist, try to find 'samples' as a fallback
    if args.input == "input_folder" and not os.path.exists(args.input):
        if os.path.exists("samples"):
            print("[*] 'input_folder' not found. Defaulting to 'samples/' directory.")
            args.input = "samples"
        else:
            print("[!] Error: No input directory found. Please specify a folder containing images or PDFs.")
            print("Usage: uv run scan_process.py <input_folder> <output_folder>")
            return
    elif not os.path.exists(args.input):
        print(f"[!] Error: Input directory '{args.input}' does not exist.")
        return

    if not os.path.exists(args.output):
        print(f"[*] Creating output directory: {args.output}")
        os.makedirs(args.output)
        
    files = [os.path.join(args.input, f) for f in os.listdir(args.input) 
             if os.path.isfile(os.path.join(args.input, f)) and 
             os.path.splitext(f)[1].lower() in ['.jpg', '.jpeg', '.png', '.webp', '.pdf', '.tiff']]
    
    if not files:
        print("No valid files found in input folder.")
        return

    print(f"Found {len(files)} files. Starting batch processing with 4 workers...")
    
    jobs = [(f, args.output, args) for f in files]
    
    with ProcessPoolExecutor(max_workers=4) as executor:
        # Wrap in list to force execution and capture exceptions
        list(executor.map(run_job, jobs))

if __name__ == "__main__":
    main()
