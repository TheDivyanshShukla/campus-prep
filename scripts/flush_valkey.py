import os
import redis
from dotenv import load_dotenv

load_dotenv()

def flush_valkey():
    # Get connection strings from env or use defaults (matching settings.py fixes)
    broker_url = os.getenv('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
    cache_url = os.getenv('CACHE_URL', 'redis://127.0.0.1:6379/1')

    # Flush DB 0 (Celery)
    try:
        r0 = redis.from_url(broker_url)
        r0.flushdb()
        print(f"✅ Flushed Celery DB (0) at {broker_url}")
    except Exception as e:
        print(f"❌ Error flushing Celery DB: {e}")

    # Flush DB 1 (Cache)
    try:
        r1 = redis.from_url(cache_url)
        r1.flushdb()
        print(f"✅ Flushed Cache DB (1) at {cache_url}")
    except Exception as e:
        print(f"❌ Error flushing Cache DB: {e}")

    # Optional: Flush ALL databases on the host
    try:
        host = broker_url.split('@')[-1].split('/')[0] if '@' in broker_url else broker_url.split('//')[-1].split('/')[0]
        host_ip = host.split(':')[0]
        port = int(host.split(':')[1]) if ':' in host else 6379
        
        r_all = redis.Redis(host=host_ip, port=port)
        r_all.flushall()
        print(f"🔥 FLUSHALL executed on {host_ip}:{port}")
    except Exception as e:
        print(f"❌ Error during FLUSHALL: {e}")

if __name__ == "__main__":
    flush_valkey()
