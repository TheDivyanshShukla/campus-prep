from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction, IntegrityError, DataError
from django.db.models import ForeignKey
from django.db.models import TextField, CharField, JSONField
from django.conf import settings
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Exclude framework and heavy perf tables (silk) from migration
EXCLUDED_MODELS = {
    'contenttypes.contenttype',
    'auth.permission',
    'admin.logentry',
    'sessions.session',
    'silk.request',
    'silk.response',
    'silk.sqlquery',
}


def clean_json(value):
    if isinstance(value, str):
        return value.replace('\x00', '').replace('\\u0000', '')
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, dict):
        return {k: clean_json(v) for k, v in value.items()}
    return value


def clean_value(value):
    if isinstance(value, str):
        return value.replace('\x00', '').replace('\\u0000', '')
    if isinstance(value, (list, dict)):
        return clean_json(value)
    return value


def model_label(m):
    return f"{m._meta.app_label}.{m._meta.model_name}"


def build_dependency_graph(models):
    deps = {model: set() for model in models}
    label_map = {model_label(m): m for m in models}
    for m in models:
        for f in m._meta.get_fields():
            if isinstance(f, ForeignKey):
                rel = f.remote_field.model
                try:
                    rel_label = model_label(rel)
                except Exception:
                    rel_label = f.remote_field.model
                if rel_label in label_map:
                    deps[m].add(label_map[rel_label])
    return deps


def topological_sort(models, deps):
    incoming = {m: set(deps.get(m, set())) for m in models}
    outgoing = {m: set() for m in models}
    for m, ds in deps.items():
        for d in ds:
            outgoing.setdefault(d, set()).add(m)

    no_incoming = [m for m, inc in incoming.items() if not inc]
    order = []
    while no_incoming:
        n = no_incoming.pop()
        order.append(n)
        for m in list(outgoing.get(n, [])):
            incoming[m].discard(n)
            if not incoming[m]:
                no_incoming.append(m)

    remaining = [m for m, inc in incoming.items() if inc]
    return order, set(remaining)


class Command(BaseCommand):
    help = 'Copy data from `legacy` (sqlite) DB to default Postgres DB. Skips silk tables and uses bulk writes.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Do not write to target DB')
        parser.add_argument('--batch-size', type=int, default=500, help='Batch size for bulk operations')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        batch_size = options.get('batch_size')

        if 'legacy' not in settings.DATABASES:
            default_engine = settings.DATABASES.get('default', {}).get('ENGINE', '')
            if 'sqlite' in default_engine:
                self.stderr.write(self.style.ERROR("No separate 'legacy' DB configured and default is sqlite — nothing to migrate."))
                return

            base = Path(getattr(settings, 'BASE_DIR', Path.cwd()))
            candidates = [base / 'data' / 'db.sqlite3', base / 'db.sqlite3']
            found = None
            for p in candidates:
                if p.exists():
                    found = p
                    break
            if not found:
                self.stderr.write(self.style.ERROR("Couldn't find legacy sqlite DB. Configure 'legacy' in DATABASES or place a sqlite DB at data/db.sqlite3"))
                return
            settings.DATABASES['legacy'] = {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': str(found),
                'TIME_ZONE': getattr(settings, 'TIME_ZONE', None),
                'AUTOCOMMIT': True,
                'ATOMIC_REQUESTS': False,
                'CONN_MAX_AGE': 0,
                'CONN_HEALTH_CHECKS': [],
                'OPTIONS': {},
            }
            self.stdout.write(f"Auto-configured legacy DB at {found}")

        all_models = [m for m in apps.get_models() if not m._meta.proxy]
        models = [m for m in all_models if model_label(m) not in EXCLUDED_MODELS]

        deps = build_dependency_graph(models)
        order, cycles = topological_sort(models, deps)

        self.stdout.write(f"Models to copy: {len(models)}; order: {len(order)}; cycles: {len(cycles)}; dry_run={dry_run}")

        inserted = {model_label(m): set() for m in models}
        deferred_updates = []
        total_inserted = 0

        def copy_model_bulk(m):
            nonlocal total_inserted
            label = model_label(m)
            qs = m.objects.using('legacy').all()
            total = qs.count()
            if total == 0:
                return 0, 0
            self.stdout.write(f"Processing {label} ({total} rows) with bulk_create")

            batch_instances = []
            batch_pks = []
            processed = 0
            failures = 0

            for obj in qs.iterator():
                pk = getattr(obj, m._meta.pk.attname)
                inst_kwargs = {}
                for field in m._meta.concrete_fields:
                    if field.primary_key:
                        continue
                    if field.auto_created and not field.primary_key:
                        continue
                    if isinstance(field, ForeignKey):
                        ref_pk = getattr(obj, f"{field.name}_id")
                        if ref_pk is None:
                            inst_kwargs[field.attname] = None
                        else:
                            rel_model = field.remote_field.model
                            try:
                                rel_label = model_label(rel_model)
                            except Exception:
                                rel_label = field.remote_field.model
                            if rel_label in inserted and ref_pk in inserted[rel_label]:
                                inst_kwargs[field.attname] = ref_pk
                            elif apps.is_installed(rel_model._meta.app_label) and rel_model.objects.using('default').filter(pk=ref_pk).exists():
                                inst_kwargs[field.attname] = ref_pk
                            else:
                                inst_kwargs[field.attname] = None
                                deferred_updates.append((m, pk, field.attname, rel_label, ref_pk))
                    else:
                        val = getattr(obj, field.attname)
                        if isinstance(field, JSONField) or isinstance(field, (TextField, CharField)):
                            try:
                                val = clean_value(val)
                            except Exception:
                                try:
                                    val = str(val).replace('\x00', '').replace('\\u0000', '')
                                except Exception:
                                    val = None
                        inst_kwargs[field.attname] = val

                if dry_run:
                    processed += 1
                    continue

                try:
                    instance = m(**inst_kwargs)
                    # set PK explicitly
                    setattr(instance, m._meta.pk.attname, pk)
                    batch_instances.append(instance)
                    batch_pks.append(pk)
                except Exception as e:
                    failures += 1
                    self.stderr.write(f"Failed to construct instance {label} pk={pk}: {e}")

                if len(batch_instances) >= batch_size:
                    try:
                        m.objects.using('default').bulk_create(batch_instances, batch_size=batch_size, ignore_conflicts=True)
                        # mark inserted pks that now exist in target
                        existing = set(m.objects.using('default').filter(pk__in=batch_pks).values_list('pk', flat=True))
                        inserted[label].update(existing)
                        total_inserted += len(existing)
                        processed += len(batch_instances)
                    except DataError as e:
                        # try per-row fallback for this batch
                        for inst, pk in zip(batch_instances, batch_pks):
                            try:
                                with transaction.atomic(using='default'):
                                    m.objects.using('default').update_or_create(pk=pk, defaults={f.name: getattr(inst, f.name) for f in m._meta.concrete_fields if not f.primary_key and not f.auto_created})
                                    inserted[label].add(pk)
                                    total_inserted += 1
                                    processed += 1
                            except Exception as e2:
                                failures += 1
                                self.stderr.write(f"Row fallback failed {label} pk={pk}: {e2}")
                    finally:
                        batch_instances = []
                        batch_pks = []

            # flush remaining
            if batch_instances:
                try:
                    m.objects.using('default').bulk_create(batch_instances, batch_size=batch_size, ignore_conflicts=True)
                    existing = set(m.objects.using('default').filter(pk__in=batch_pks).values_list('pk', flat=True))
                    inserted[label].update(existing)
                    total_inserted += len(existing)
                    processed += len(batch_instances)
                except DataError as e:
                    for inst, pk in zip(batch_instances, batch_pks):
                        try:
                            with transaction.atomic(using='default'):
                                m.objects.using('default').update_or_create(pk=pk, defaults={f.name: getattr(inst, f.name) for f in m._meta.concrete_fields if not f.primary_key and not f.auto_created})
                                inserted[label].add(pk)
                                total_inserted += 1
                                processed += 1
                        except Exception as e2:
                            failures += 1
                            self.stderr.write(f"Row fallback failed {label} pk={pk}: {e2}")

            self.stdout.write(f"Processed {processed}/{total} for {label} (failures={failures})")
            return processed, failures

        # main copy passes
        for m in order:
            copy_model_bulk(m)

        if cycles:
            self.stdout.write(f"Processing cyclic models ({len(cycles)}) in arbitrary order")
            for m in cycles:
                copy_model_bulk(m)

        # resolve deferred FK updates
        self.stdout.write(f"Attempting to resolve {len(deferred_updates)} deferred FK updates")
        unresolved = []
        resolved = 0
        for m, pk, attname, target_label, target_pk in deferred_updates:
            try:
                if target_pk is None:
                    continue
                app_label, model_name = target_label.split('.') if isinstance(target_label, str) and '.' in target_label else (None, None)
                if app_label and model_name:
                    target_model = apps.get_model(app_label, model_name)
                    if target_model.objects.using('default').filter(pk=target_pk).exists():
                        apps.get_model(m._meta.app_label, m._meta.model_name).objects.using('default').filter(pk=pk).update(**{attname: target_pk})
                        resolved += 1
                        continue
                # if we reach here, unresolved
                unresolved.append((m, pk, attname, target_label, target_pk))
            except Exception:
                unresolved.append((m, pk, attname, target_label, target_pk))

        self.stdout.write(f"Resolved deferred FK updates: {resolved}; remaining: {len(unresolved)}")

        # M2M copying: ensure related targets exist
        for m in models:
            m2m_fields = [f for f in m._meta.many_to_many]
            if not m2m_fields:
                continue
            lbl = model_label(m)
            self.stdout.write(f"Copying M2M for {lbl}")
            for obj in m.objects.using('legacy').all().iterator():
                pk = getattr(obj, m._meta.pk.attname)
                try:
                    target_obj = m.objects.using('default').get(pk=pk)
                except m.DoesNotExist:
                    continue
                for m2m in m2m_fields:
                    try:
                        related_model = m2m.remote_field.model
                        related_pks = list(getattr(obj, m2m.name).all().values_list('pk', flat=True))
                        valid = [p for p in related_pks if related_model.objects.using('default').filter(pk=p).exists()]
                        getattr(target_obj, m2m.name).set(valid)
                    except Exception as e:
                        self.stderr.write(f"Failed M2M copy {lbl}.{m2m.name} pk={pk}: {e}")

        if unresolved:
            self.stderr.write("Warning: some FK references could not be resolved. See log for details.")
            for item in unresolved[:100]:
                m, pk, attname, target_label, target_pk = item
                self.stderr.write(f"Unresolved: {model_label(m)} pk={pk} field={attname} -> {target_label}:{target_pk}")
        else:
            self.stdout.write(self.style.SUCCESS('All FK references resolved'))

        self.stdout.write(self.style.SUCCESS(f'Done. Inserted approx {total_inserted} rows.'))
