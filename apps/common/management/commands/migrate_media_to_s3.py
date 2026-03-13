from django.core.management.base import BaseCommand
from django.conf import settings
import os
import mimetypes
import boto3
from botocore.exceptions import BotoCoreError, ClientError


class Command(BaseCommand):
    help = "Upload files from MEDIA_ROOT to configured S3-compatible bucket."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='List files that would be uploaded')
        parser.add_argument('--prefix', default='', help='Key prefix to use in the bucket')
        parser.add_argument('--bucket', default='', help='Override bucket name (defaults to AWS_STORAGE_BUCKET_NAME)')

    def handle(self, *args, **options):
        media_root = getattr(settings, 'MEDIA_ROOT', None)
        if not media_root or not os.path.isdir(media_root):
            self.stderr.write(self.style.ERROR(f"MEDIA_ROOT not found or is not a directory: {media_root}"))
            return

        bucket = options.get('bucket') or getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None) or os.getenv('AWS_STORAGE_BUCKET_NAME')
        if not bucket:
            self.stderr.write(self.style.ERROR('Bucket name not configured. Set AWS_STORAGE_BUCKET_NAME in env or pass --bucket.'))
            return

        access_key = os.getenv('AWS_ACCESS_KEY_ID') or getattr(settings, 'AWS_ACCESS_KEY_ID', None)
        secret_key = os.getenv('AWS_SECRET_ACCESS_KEY') or getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        endpoint = os.getenv('AWS_S3_ENDPOINT_URL') or getattr(settings, 'AWS_S3_ENDPOINT_URL', None)
        region = os.getenv('AWS_S3_REGION_NAME') or getattr(settings, 'AWS_S3_REGION_NAME', None)

        if not (access_key and secret_key and endpoint):
            self.stderr.write(self.style.ERROR('S3 credentials or endpoint missing in environment (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_S3_ENDPOINT_URL).'))
            return

        dry_run = options.get('dry_run')
        prefix = options.get('prefix') or ''

        session = boto3.session.Session()
        s3 = session.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region if region else None,
            endpoint_url=endpoint,
        )

        uploaded = 0
        errors = 0

        for root, dirs, files in os.walk(media_root):
            for filename in files:
                local_path = os.path.join(root, filename)
                rel_path = os.path.relpath(local_path, media_root)
                key = os.path.join(prefix, rel_path).replace('\\', '/')

                content_type, _ = mimetypes.guess_type(local_path)
                extra_args = {}
                if content_type:
                    extra_args['ContentType'] = content_type

                if dry_run:
                    self.stdout.write(f"DRY: {local_path} -> {bucket}/{key}")
                    continue

                try:
                    s3.upload_file(local_path, bucket, key, ExtraArgs=extra_args)
                    uploaded += 1
                    if uploaded % 100 == 0:
                        self.stdout.write(f"Uploaded {uploaded} files...")
                except (BotoCoreError, ClientError) as exc:
                    errors += 1
                    self.stderr.write(self.style.ERROR(f"Failed to upload {local_path}: {exc}"))

        self.stdout.write(self.style.SUCCESS(f"Done. Uploaded={uploaded} Errors={errors}"))
