import json
import time
import traceback
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.content.models import ParsedDocument
from apps.content.tasks import process_document_ai


class Command(BaseCommand):
    help = (
        "Dispatch ParsedDocument records to Celery for AI parsing (native view conversion). "
        "Supports resume, rate limiting, and automatic FAILED-doc reset."
    )

    # ------------------------------------------------------------------ #
    # Arguments                                                            #
    # ------------------------------------------------------------------ #
    def add_arguments(self, parser):
        parser.add_argument(
            "--document-types",
            nargs="+",
            default=["UNSOLVED_PYQ"],
            help="Document types to process (default: UNSOLVED_PYQ)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max number of documents to dispatch in this run",
        )
        parser.add_argument(
            "--start-id",
            type=int,
            default=None,
            help="Only consider docs with id >= this value",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview which docs would be dispatched without actually queuing tasks",
        )
        parser.add_argument(
            "--resume",
            dest="resume",
            action="store_true",
            help="(default) Skip docs already marked COMPLETED in DB",
        )
        parser.add_argument(
            "--no-resume",
            dest="resume",
            action="store_false",
            help="Queue ALL matching docs, ignoring COMPLETED status",
        )
        parser.add_argument(
            "--reset-failed",
            dest="reset_failed",
            action="store_true",
            help="(default) Reset FAILED docs back to PENDING so they get re-queued",
        )
        parser.add_argument(
            "--no-reset-failed",
            dest="reset_failed",
            action="store_false",
            help="Skip docs currently in FAILED status",
        )
        parser.add_argument(
            "--force-requeue-processing",
            action="store_true",
            help="Also re-queue docs stuck as PROCESSING (treat them as stale/crashed)",
        )
        parser.add_argument(
            "--rate",
            type=float,
            default=100.0,
            help="Max Celery tasks to dispatch per second (default: 100)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=200,
            help="DB query chunk size for iterating documents (default: 200)",
        )
        parser.add_argument(
            "--state-file",
            default=None,
            help="Path to the JSON resume-state file (auto-located by default)",
        )
        parser.add_argument(
            "--reset-state",
            action="store_true",
            help="Delete the existing state file before this run (start fresh)",
        )
        parser.add_argument(
            "--log-dir",
            default=None,
            help="Directory for per-run and per-error log files",
        )
        parser.set_defaults(resume=True, reset_failed=True)

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #
    def _default_state_file(self):
        return Path(settings.BASE_DIR) / "data" / "dispatch_ai_parse_state.json"

    def _default_log_dir(self):
        return Path(settings.BASE_DIR) / "data" / "logs" / "dispatch_ai_parse"

    def _load_state(self, state_file: Path) -> dict:
        if not state_file.exists():
            return {"dispatched": {}, "last_run": None}
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            return {"dispatched": {}, "last_run": None}

    def _save_state(self, state_file: Path, state: dict):
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def _log(self, log_file: Path, message: str):
        log_file.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{ts} UTC] {message}\n")

    # ------------------------------------------------------------------ #
    # Main handler                                                         #
    # ------------------------------------------------------------------ #
    def handle(self, *args, **options):
        state_file = Path(options["state_file"]) if options["state_file"] else self._default_state_file()
        log_dir = Path(options["log_dir"]) if options["log_dir"] else self._default_log_dir()
        run_tag = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        run_log = log_dir / f"run_{run_tag}.log"
        err_log = log_dir / f"errors_{run_tag}.log"

        # Optionally wipe state
        if options["reset_state"] and state_file.exists():
            state_file.unlink()
            self.stdout.write(self.style.WARNING("State file deleted."))

        state = self._load_state(state_file)
        # Previously dispatched IDs (for intra-run deduplication)
        prev_dispatched_ids = set(int(k) for k in state.get("dispatched", {}).keys()) if options["resume"] else set()

        # ---------------------------------------------------------------- #
        # Build the queryset                                                #
        # ---------------------------------------------------------------- #
        allowed_statuses = ["PENDING"]
        if options["reset_failed"]:
            allowed_statuses.append("FAILED")
        if options["force_requeue_processing"]:
            allowed_statuses.append("PROCESSING")

        queryset = (
            ParsedDocument.objects
            .filter(
                document_type__in=options["document_types"],
                source_file__isnull=False,
            )
            .exclude(source_file="")
        )

        # Resume: exclude already COMPLETED docs from consideration
        if options["resume"]:
            queryset = queryset.exclude(parsing_status="COMPLETED")

        queryset = queryset.filter(parsing_status__in=allowed_statuses).order_by("id")

        if options["start_id"] is not None:
            queryset = queryset.filter(id__gte=options["start_id"])

        if options["limit"]:
            queryset = queryset[: options["limit"]]

        docs = list(queryset.values("id", "parsing_status", "title"))

        if not docs:
            self.stdout.write(self.style.SUCCESS("No matching documents found."))
            return

        # Intra-run resume: skip docs already dispatched in a previous session
        if prev_dispatched_ids:
            before = len(docs)
            docs = [d for d in docs if d["id"] not in prev_dispatched_ids]
            skipped_resume = before - len(docs)
            if skipped_resume:
                self.stdout.write(
                    self.style.NOTICE(f"Resume: skipped {skipped_resume} already dispatched docs.")
                )

        if not docs:
            self.stdout.write(self.style.SUCCESS("All selected docs already dispatched per state file."))
            return

        # ---------------------------------------------------------------- #
        # Pre-flight: reset FAILED → PENDING in bulk                       #
        # ---------------------------------------------------------------- #
        if options["reset_failed"] and not options["dry_run"]:
            failed_ids = [d["id"] for d in docs if d["parsing_status"] == "FAILED"]
            if failed_ids:
                updated = ParsedDocument.objects.filter(id__in=failed_ids).update(parsing_status="PENDING")
                self.stdout.write(self.style.NOTICE(f"Reset {updated} FAILED docs → PENDING."))
                self._log(run_log, f"Reset {updated} FAILED docs to PENDING: ids={failed_ids}")

        # Also reset stuck PROCESSING docs if requested
        if options["force_requeue_processing"] and not options["dry_run"]:
            stuck_ids = [d["id"] for d in docs if d["parsing_status"] == "PROCESSING"]
            if stuck_ids:
                updated = ParsedDocument.objects.filter(id__in=stuck_ids).update(parsing_status="PENDING")
                self.stdout.write(self.style.NOTICE(f"Reset {updated} stuck PROCESSING docs → PENDING."))
                self._log(run_log, f"Reset {updated} stuck PROCESSING docs: ids={stuck_ids}")

        total = len(docs)
        self.stdout.write(
            self.style.NOTICE(
                f"Dispatching {total} documents "
                f"(types={options['document_types']}, rate={options['rate']}/s, dry_run={options['dry_run']})"
            )
        )
        self._log(run_log, f"Run started: total={total}, dry_run={options['dry_run']}, resume={options['resume']}, rate={options['rate']}")

        # ---------------------------------------------------------------- #
        # Dispatch loop                                                     #
        # ---------------------------------------------------------------- #
        rate = max(0.01, options["rate"])
        min_interval = 1.0 / rate  # seconds per task
        dispatched = 0
        errors = 0
        SAVE_EVERY = 50  # persist state every N dispatches

        for i, doc in enumerate(docs):
            doc_id = doc["id"]
            doc_title = doc["title"]
            loop_start = time.monotonic()

            if options["dry_run"]:
                self.stdout.write(f"[DRY-RUN] id={doc_id}  '{doc_title}'")
            else:
                try:
                    process_document_ai.apply_async(args=[doc_id])
                    dispatched += 1

                    state.setdefault("dispatched", {})[str(doc_id)] = {
                        "title": doc_title,
                        "at": datetime.utcnow().isoformat() + "Z",
                    }
                    self._log(run_log, f"DISPATCHED id={doc_id} title={doc_title}")

                except Exception as exc:
                    errors += 1
                    self.stdout.write(self.style.ERROR(f"[ERROR] id={doc_id}: {exc}"))
                    self._log(err_log, f"ERROR id={doc_id} title={doc_title} error={exc}")
                    self._log(err_log, traceback.format_exc())

            # Progress
            if (i + 1) % SAVE_EVERY == 0 or (i + 1) == total:
                self.stdout.write(
                    f"[PROGRESS] {i + 1}/{total} | dispatched={dispatched} errors={errors}"
                )
                if not options["dry_run"]:
                    state["last_run"] = datetime.utcnow().isoformat() + "Z"
                    self._save_state(state_file, state)

            # Rate limiting
            if not options["dry_run"]:
                elapsed = time.monotonic() - loop_start
                sleep_time = min_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        # Final state flush
        if not options["dry_run"]:
            state["last_run"] = datetime.utcnow().isoformat() + "Z"
            self._save_state(state_file, state)

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"Dry run complete. Would dispatch {total} documents."))
        else:
            self.stdout.write(self.style.SUCCESS("Dispatch complete."))

        self.stdout.write(
            f"Summary: dispatched={dispatched}, errors={errors}, total={total}"
        )
        self.stdout.write(f"State file : {state_file}")
        self.stdout.write(f"Run log    : {run_log}")
        if errors:
            self.stdout.write(f"Error log  : {err_log}")
        self._log(run_log, f"Run finished: dispatched={dispatched}, errors={errors}, total={total}")
