import os
import shutil
import sys
import tempfile
import json
import traceback
import importlib
import threading
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import fitz

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from apps.content.models import ParsedDocument


class Command(BaseCommand):
    help = "Download PDFs from storage, convert via datamine OCR pipeline, and re-upload/update ParsedDocument.source_file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--document-types",
            nargs="+",
            default=["UNSOLVED_PYQ"],
            help="Document types to process (default: UNSOLVED_PYQ)",
        )
        parser.add_argument("--limit", type=int, default=None, help="Maximum number of documents to process")
        parser.add_argument("--start-id", type=int, default=None, help="Only process docs with id >= start-id")
        parser.add_argument("--dry-run", action="store_true", help="Preview actions without writing to storage")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Overwrite original source_file path in storage (deletes old object first)",
        )
        parser.add_argument(
            "--suffix",
            default="-ocr",
            help="Suffix for converted filenames when not using --overwrite (default: -ocr)",
        )
        parser.add_argument("--no-enhance", action="store_true", help="Pass through to scanner pipeline")
        parser.add_argument("--dpi", type=int, default=300, help="Fallback DPI for scanner pipeline")
        parser.add_argument("--ocr-lang", default="eng", help="OCR language, e.g. eng or eng+hin")
        parser.add_argument("--ocr-psm", type=int, default=11, help="Tesseract PSM mode")
        parser.add_argument(
            "--ocr-border-clean-px",
            type=int,
            default=10,
            help="OCR-only border cleanup in pixels",
        )
        parser.add_argument(
            "--keep-temp",
            action="store_true",
            help="Keep temporary conversion directory for debugging",
        )
        parser.add_argument(
            "--resume",
            dest="resume",
            action="store_true",
            help="Resume from state file and skip already successful docs",
        )
        parser.add_argument(
            "--no-resume",
            dest="resume",
            action="store_false",
            help="Ignore resume state and process selected docs again",
        )
        parser.add_argument(
            "--state-file",
            default=None,
            help="Path to resume state JSON file",
        )
        parser.add_argument(
            "--reset-state",
            action="store_true",
            help="Delete existing state before run",
        )
        parser.add_argument(
            "--log-dir",
            default=None,
            help="Directory for run and error logs",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=None,
            help="Parallel workers for conversion (default: CPU core count)",
        )
        parser.set_defaults(resume=True)

    def _default_state_file(self):
        return Path(settings.BASE_DIR) / "data" / "reprocess_pdf_assets_state.json"

    def _default_log_dir(self):
        return Path(settings.BASE_DIR) / "data" / "logs" / "reprocess_pdf_assets"

    def _load_state(self, state_file: Path):
        if not state_file.exists():
            return {"completed": {}, "failed": {}, "last_run": None}
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            return {"completed": {}, "failed": {}, "last_run": None}

    def _save_state(self, state_file: Path, state: dict):
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def _append_log(self, log_file: Path, message: str):
        log_file.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{ts} UTC] {message}\n")

    def _build_scan_args(self, options):
        return Namespace(
            mode="color",
            dpi=options["dpi"],
            preserve_source_dpi=True,
            ocr_lang=options["ocr_lang"],
            ocr_mode="lossless",
            ocr_psm=options["ocr_psm"],
            ocr_border_clean_px=options["ocr_border_clean_px"],
            remove_footer=0,
            remove_black_blobs=True,
            black_blob_padding=2,
            black_blob_area_multiplier=1.0,
            black_blob_density_threshold=0.45,
            remove_footer_link=True,
            footer_link_box_width_ratio=0.62,
            footer_link_box_height_ratio=0.075,
            footer_link_bottom_margin_ratio=0.0,
            watermark_text="rgpv.online.com",
            watermark_opacity=0.26,
            watermark_font_scale=1.0,
            watermark_thickness=2,
            watermark_bottom_margin_px=12,
            save_images=False,
            linearize=True,
            ocr=True,
            no_enhance=options["no_enhance"],
            tesseract_path=None,
            config=None,
        )

    def _load_scan_processor(self, scan_args):
        datamine_dir = Path(settings.BASE_DIR) / ".me" / "datamine"
        if not datamine_dir.exists():
            raise RuntimeError(f"Datamine directory not found: {datamine_dir}")

        if str(datamine_dir) not in sys.path:
            sys.path.insert(0, str(datamine_dir))

        scan_module = importlib.import_module("scan_process")
        ScanProcessorCLI = getattr(scan_module, "ScanProcessorCLI")
        return ScanProcessorCLI(scan_args)

    def _target_storage_name(self, original_name, suffix, overwrite):
        normalized = str(original_name).replace("\\", "/")
        upload_prefix = "raw_docs/"
        while normalized.startswith(upload_prefix):
            normalized = normalized[len(upload_prefix):]

        original_path = Path(normalized)
        if overwrite:
            return str(original_path).replace("\\", "/")
        new_name = f"{original_path.stem}{suffix}{original_path.suffix}"
        return str(original_path.with_name(new_name)).replace("\\", "/")

    def _optimize_pdf_bytes(self, pdf_bytes: bytes):
        original_size = len(pdf_bytes)
        try:
            with fitz.open(stream=pdf_bytes, filetype="pdf") as src_doc:
                optimized_bytes = src_doc.tobytes(garbage=4, deflate=True, clean=True)

            optimized_size = len(optimized_bytes)
            if optimized_size > 0 and optimized_size < original_size:
                return optimized_bytes, {
                    "optimized": True,
                    "before": original_size,
                    "after": optimized_size,
                }

            return pdf_bytes, {
                "optimized": False,
                "before": original_size,
                "after": original_size,
            }
        except Exception:
            return pdf_bytes, {
                "optimized": False,
                "before": original_size,
                "after": original_size,
            }

    def _process_one_doc(self, doc_id, source_name, target_name, temp_root, options, get_processor):
        close_old_connections()
        doc_tmp = temp_root / f"doc_{doc_id}"
        in_dir = doc_tmp / "in"
        out_dir = doc_tmp / "out"
        in_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)

        input_path = in_dir / Path(source_name).name
        output_path = out_dir / f"{input_path.stem}.pdf"

        try:
            doc = ParsedDocument.objects.get(id=doc_id)

            with doc.source_file.storage.open(source_name, "rb") as src_file:
                input_path.write_bytes(src_file.read())

            processor = get_processor()
            processor.process_single_file(str(input_path), str(out_dir))

            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError("Converted output PDF not found or empty")

            converted_bytes = output_path.read_bytes()
            converted_bytes, optimize_meta = self._optimize_pdf_bytes(converted_bytes)

            # Optimization: Skip .exists() check before .delete(). 
            # S3/Boto3 delete is idempotent (returns 204 if missing) and saves a HEAD operation.
            try:
                doc.source_file.storage.delete(target_name)
            except Exception:
                pass

            doc.source_file.save(target_name, ContentFile(converted_bytes), save=False)
            doc.save(update_fields=["source_file", "updated_at"])

            return {
                "status": "success",
                "doc_id": doc_id,
                "source": source_name,
                "target": target_name,
                "optimize_meta": optimize_meta,
            }
        except Exception as exc:
            return {
                "status": "failed",
                "doc_id": doc_id,
                "source": source_name,
                "target": target_name,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        finally:
            if doc_tmp.exists() and not options["keep_temp"]:
                shutil.rmtree(doc_tmp, ignore_errors=True)
            close_old_connections()

    def handle(self, *args, **options):
        state_file = Path(options["state_file"]) if options["state_file"] else self._default_state_file()
        log_dir = Path(options["log_dir"]) if options["log_dir"] else self._default_log_dir()
        run_tag = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        run_log_file = log_dir / f"run_{run_tag}.log"
        error_log_file = log_dir / f"errors_{run_tag}.log"

        if options["reset_state"] and state_file.exists():
            state_file.unlink()

        state = self._load_state(state_file)
        completed_ids = set(int(k) for k in state.get("completed", {}).keys()) if options["resume"] else set()

        queryset = ParsedDocument.objects.filter(
            document_type__in=options["document_types"],
            source_file__isnull=False,
        ).exclude(source_file="")

        if options["start_id"] is not None:
            queryset = queryset.filter(id__gte=options["start_id"])

        queryset = queryset.order_by("id")
        if options["limit"]:
            queryset = queryset[: options["limit"]]

        docs = list(queryset)
        if not docs:
            self.stdout.write(self.style.WARNING("No matching documents found."))
            return

        if options["resume"] and completed_ids:
            before_count = len(docs)
            docs = [doc for doc in docs if doc.id not in completed_ids]
            skipped_resumed = before_count - len(docs)
            if skipped_resumed:
                self.stdout.write(self.style.NOTICE(f"Resume enabled: skipped {skipped_resumed} already completed docs."))

        if not docs:
            self.stdout.write(self.style.SUCCESS("All selected docs are already completed in state file."))
            return

        scan_args = self._build_scan_args(options)
        workers = options["workers"] if options["workers"] else (os.cpu_count() or 1)
        workers = max(1, int(workers))
        if options["dry_run"]:
            workers = 1

        thread_local = threading.local()

        def get_processor():
            if not hasattr(thread_local, "processor"):
                thread_local.processor = self._load_scan_processor(scan_args)
            return thread_local.processor

        self.stdout.write(self.style.NOTICE(f"Selected {len(docs)} documents for reprocessing with workers={workers}."))
        self._append_log(run_log_file, f"Run started: total={len(docs)}, dry_run={options['dry_run']}, resume={options['resume']}, workers={workers}")

        success = 0
        failed = 0
        skipped = 0

        temp_root = Path(tempfile.mkdtemp(prefix="pdf_reprocess_"))
        try:
            tasks = []
            for doc in docs:
                source_name = doc.source_file.name
                if not source_name.lower().endswith(".pdf"):
                    skipped += 1
                    self.stdout.write(f"[SKIP] id={doc.id} non-pdf source: {source_name}")
                    continue

                target_name = self._target_storage_name(source_name, options["suffix"], options["overwrite"])
                self.stdout.write(f"[PROCESS] id={doc.id} {source_name} -> {target_name}")
                self._append_log(run_log_file, f"PROCESS id={doc.id} source={source_name} target={target_name}")

                if options["dry_run"]:
                    continue

                tasks.append((doc.id, source_name, target_name))

            if tasks:
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    future_map = {
                        executor.submit(
                            self._process_one_doc,
                            doc_id,
                            source_name,
                            target_name,
                            temp_root,
                            options,
                            get_processor,
                        ): (doc_id, source_name, target_name)
                        for doc_id, source_name, target_name in tasks
                    }

                    processed_count = 0
                    total_to_process = len(tasks)
                    for future in as_completed(future_map):
                        result = future.result()
                        processed_count += 1
                        doc_id = result["doc_id"]
                        source_name = result["source"]
                        target_name = result["target"]

                        if result["status"] == "success":
                            success += 1
                            state.setdefault("completed", {})[str(doc_id)] = {
                                "source": source_name,
                                "target": target_name,
                                "at": datetime.utcnow().isoformat() + "Z",
                            }
                            if str(doc_id) in state.setdefault("failed", {}):
                                del state["failed"][str(doc_id)]
                            self._append_log(run_log_file, f"SUCCESS id={doc_id} target={target_name}")
                            optimize_meta = result.get("optimize_meta") or {}
                            if optimize_meta.get("optimized"):
                                before = int(optimize_meta.get("before", 0))
                                after = int(optimize_meta.get("after", before))
                                saved = max(0, before - after)
                                self._append_log(
                                    run_log_file,
                                    f"OPTIMIZED id={doc_id} saved_mb={saved / (1024 * 1024):.2f} before_mb={before / (1024 * 1024):.2f} after_mb={after / (1024 * 1024):.2f}",
                                )
                        else:
                            failed += 1
                            err = result.get("error", "unknown error")
                            self.stdout.write(self.style.ERROR(f"[FAIL] id={doc_id}: {err}"))
                            state.setdefault("failed", {})[str(doc_id)] = {
                                "source": source_name,
                                "target": target_name,
                                "error": err,
                                "at": datetime.utcnow().isoformat() + "Z",
                            }
                            self._append_log(error_log_file, f"FAIL id={doc_id} source={source_name} target={target_name} error={err}")
                            self._append_log(error_log_file, result.get("traceback", ""))

                        state["last_run"] = datetime.utcnow().isoformat() + "Z"
                        self._save_state(state_file, state)

                        if processed_count % max(1, workers) == 0 or processed_count == total_to_process:
                            self.stdout.write(
                                f"[PROGRESS] {processed_count}/{total_to_process} done | success={success} failed={failed}"
                            )

            if options["dry_run"]:
                self.stdout.write(self.style.SUCCESS("Dry run completed (no files changed)."))
            else:
                self.stdout.write(self.style.SUCCESS("Reprocessing completed."))

            self.stdout.write(
                f"Summary: success={success}, failed={failed}, skipped={skipped}, total={len(docs)}"
            )
            self.stdout.write(f"State file: {state_file}")
            self.stdout.write(f"Run log: {run_log_file}")
            self.stdout.write(f"Error log: {error_log_file}")
            self._append_log(run_log_file, f"Run finished: success={success}, failed={failed}, skipped={skipped}, total={len(docs)}")
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Interrupted. Progress has been saved to state/log files."))
            self._append_log(run_log_file, "Run interrupted by KeyboardInterrupt")
            raise
        finally:
            if temp_root.exists() and not options["keep_temp"]:
                shutil.rmtree(temp_root, ignore_errors=True)
