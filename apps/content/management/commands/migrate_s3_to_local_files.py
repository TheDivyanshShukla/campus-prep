import json
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.db import close_old_connections
from django.utils import timezone

from apps.content.models import ParsedDocument


class Command(BaseCommand):
    help = "Download S3-backed source_file PDFs to local media/s3 and update DB paths in batches"

    def add_arguments(self, parser):
        parser.add_argument(
            "--document-types",
            nargs="+",
            default=["UNSOLVED_PYQ"],
            help="Document types to migrate (default: UNSOLVED_PYQ)",
        )
        parser.add_argument("--batch-size", type=int, default=200, help="DB batch size (default: 200)")
        parser.add_argument("--limit", type=int, default=None, help="Total max docs to process")
        parser.add_argument("--start-id", type=int, default=None, help="Only process docs with id >= start-id")
        parser.add_argument("--workers", type=int, default=32, help="Parallel workers for download/write")
        parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
        parser.add_argument("--resume", dest="resume", action="store_true", help="Resume from state file")
        parser.add_argument("--no-resume", dest="resume", action="store_false", help="Ignore resume state")
        parser.add_argument("--reset-state", action="store_true", help="Delete existing state first")
        parser.add_argument("--state-file", default=None, help="Custom state JSON path")
        parser.add_argument("--log-dir", default=None, help="Custom log directory")
        parser.set_defaults(resume=True)

    def _default_state_file(self):
        return Path(settings.BASE_DIR) / "data" / "migrate_s3_to_local_files_state.json"

    def _default_log_dir(self):
        return Path(settings.BASE_DIR) / "data" / "logs" / "migrate_s3_to_local_files"

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

    def _to_local_relpath(self, source_name: str) -> str:
        normalized = str(source_name or "").replace("\\", "/").lstrip("/")
        if normalized.startswith("s3/"):
            return normalized
        return f"s3/{normalized}"

    def _process_one(self, doc_id: int, source_name: str, local_relpath: str, dry_run: bool):
        close_old_connections()
        try:
            if dry_run:
                return {
                    "status": "success",
                    "doc_id": doc_id,
                    "source": source_name,
                    "target": local_relpath,
                    "dry_run": True,
                }

            media_root = Path(settings.MEDIA_ROOT)
            local_abs_path = media_root / local_relpath
            local_abs_path.parent.mkdir(parents=True, exist_ok=True)

            with default_storage.open(source_name, "rb") as src_file:
                local_abs_path.write_bytes(src_file.read())

            return {
                "status": "success",
                "doc_id": doc_id,
                "source": source_name,
                "target": local_relpath,
                "dry_run": False,
            }
        except Exception as exc:
            return {
                "status": "failed",
                "doc_id": doc_id,
                "source": source_name,
                "target": local_relpath,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        finally:
            close_old_connections()

    def _bulk_link(self, entries):
        """
        entries: list of dict with keys doc_id, target
        """
        if not entries:
            return

        ids = [entry["doc_id"] for entry in entries]
        docs = list(ParsedDocument.objects.filter(id__in=ids).only("id", "source_file", "updated_at"))
        doc_map = {doc.id: doc for doc in docs}
        now = timezone.now()

        to_update = []
        for entry in entries:
            doc = doc_map.get(entry["doc_id"])
            if not doc:
                continue
            doc.source_file.name = entry["target"]
            doc.updated_at = now
            to_update.append(doc)

        if to_update:
            ParsedDocument.objects.bulk_update(to_update, ["source_file", "updated_at"], batch_size=1000)

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
        docs = list(queryset)

        if options["resume"] and completed_ids:
            before_count = len(docs)
            docs = [doc for doc in docs if doc.id not in completed_ids]
            skipped_resumed = before_count - len(docs)
            if skipped_resumed:
                self.stdout.write(self.style.NOTICE(f"Resume enabled: skipped {skipped_resumed} completed docs."))

        if options["limit"] is not None:
            docs = docs[: int(options["limit"])]

        if not docs:
            self.stdout.write(self.style.SUCCESS("No docs left to migrate for the selected filter."))
            return

        batch_size = max(1, int(options["batch_size"]))
        workers = max(1, int(options["workers"]))
        if options["dry_run"]:
            workers = 1

        self.stdout.write(self.style.NOTICE(f"Selected {len(docs)} docs. batch_size={batch_size}, workers={workers}"))
        self._append_log(
            run_log_file,
            f"Run started total={len(docs)} batch_size={batch_size} workers={workers} dry_run={options['dry_run']} resume={options['resume']}",
        )

        success = 0
        failed = 0
        skipped = 0
        processed = 0

        state_lock = threading.Lock()

        for batch_start in range(0, len(docs), batch_size):
            batch_docs = docs[batch_start : batch_start + batch_size]
            self.stdout.write(f"[BATCH] {batch_start + 1}-{batch_start + len(batch_docs)} / {len(docs)}")

            tasks = []
            for doc in batch_docs:
                source_name = doc.source_file.name
                if not source_name.lower().endswith(".pdf"):
                    skipped += 1
                    self.stdout.write(f"[SKIP] id={doc.id} non-pdf source: {source_name}")
                    continue

                local_relpath = self._to_local_relpath(source_name)
                self._append_log(run_log_file, f"PROCESS id={doc.id} source={source_name} target={local_relpath}")
                tasks.append((doc.id, source_name, local_relpath))

            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {
                    executor.submit(self._process_one, doc_id, source_name, local_relpath, options["dry_run"]): (doc_id, source_name, local_relpath)
                    for doc_id, source_name, local_relpath in tasks
                }

                successful_entries = []

                for future in as_completed(future_map):
                    result = future.result()
                    processed += 1
                    doc_id = result["doc_id"]
                    source_name = result["source"]
                    local_relpath = result["target"]

                    with state_lock:
                        if result["status"] == "success":
                            success += 1
                            if not options["dry_run"]:
                                successful_entries.append(result)
                            if not options["dry_run"]:
                                state.setdefault("completed", {})[str(doc_id)] = {
                                    "source": source_name,
                                    "target": local_relpath,
                                    "at": datetime.utcnow().isoformat() + "Z",
                                }
                                if str(doc_id) in state.setdefault("failed", {}):
                                    del state["failed"][str(doc_id)]
                            self._append_log(run_log_file, f"SUCCESS id={doc_id} target={local_relpath}")
                        else:
                            failed += 1
                            err = result.get("error", "unknown error")
                            self.stdout.write(self.style.ERROR(f"[FAIL] id={doc_id}: {err}"))
                            if not options["dry_run"]:
                                state.setdefault("failed", {})[str(doc_id)] = {
                                    "source": source_name,
                                    "target": local_relpath,
                                    "error": err,
                                    "at": datetime.utcnow().isoformat() + "Z",
                                }
                            self._append_log(error_log_file, f"FAIL id={doc_id} source={source_name} target={local_relpath} error={err}")
                            self._append_log(error_log_file, result.get("traceback", ""))

                        if not options["dry_run"]:
                            state["last_run"] = datetime.utcnow().isoformat() + "Z"
                            self._save_state(state_file, state)

                if not options["dry_run"] and successful_entries:
                    self._bulk_link(successful_entries)

            self.stdout.write(f"[BATCH DONE] processed={processed} success={success} failed={failed} skipped={skipped}")

        self.stdout.write(self.style.SUCCESS("Migration run completed."))
        self.stdout.write(f"Summary: success={success}, failed={failed}, skipped={skipped}, total={len(docs)}")
        self.stdout.write(f"State file: {state_file}")
        self.stdout.write(f"Run log: {run_log_file}")
        self.stdout.write(f"Error log: {error_log_file}")
        self._append_log(run_log_file, f"Run finished success={success} failed={failed} skipped={skipped} total={len(docs)}")
