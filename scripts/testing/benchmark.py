import argparse
import statistics
import time
from dataclasses import dataclass

import httpx


@dataclass
class RunStats:
    path: str
    total: int
    success: int
    failures: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * q
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    weight = rank - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


def run_benchmark(
    base_url: str,
    path: str,
    requests_count: int,
    warmup_count: int,
    timeout_seconds: float,
) -> RunStats:
    latencies_ms: list[float] = []
    success = 0
    failures = 0

    with httpx.Client(base_url=base_url, timeout=timeout_seconds, follow_redirects=True) as client:
        for _ in range(warmup_count):
            try:
                client.get(path)
            except Exception:
                pass

        for _ in range(requests_count):
            start = time.perf_counter()
            try:
                response = client.get(path)
                elapsed_ms = (time.perf_counter() - start) * 1000
                latencies_ms.append(elapsed_ms)
                if response.status_code < 500:
                    success += 1
                else:
                    failures += 1
            except Exception:
                elapsed_ms = (time.perf_counter() - start) * 1000
                latencies_ms.append(elapsed_ms)
                failures += 1

    return RunStats(
        path=path,
        total=requests_count,
        success=success,
        failures=failures,
        mean_ms=statistics.mean(latencies_ms) if latencies_ms else 0.0,
        p50_ms=percentile(latencies_ms, 0.50),
        p95_ms=percentile(latencies_ms, 0.95),
        min_ms=min(latencies_ms) if latencies_ms else 0.0,
        max_ms=max(latencies_ms) if latencies_ms else 0.0,
    )


def format_row(stats: RunStats) -> str:
    return (
        f"{stats.path:<24} "
        f"{stats.total:>7} "
        f"{stats.success:>8} "
        f"{stats.failures:>8} "
        f"{stats.mean_ms:>10.2f} "
        f"{stats.p50_ms:>10.2f} "
        f"{stats.p95_ms:>10.2f} "
        f"{stats.min_ms:>10.2f} "
        f"{stats.max_ms:>10.2f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark HTTP endpoints for django-silk overhead checks.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Server base URL")
    parser.add_argument(
        "--paths",
        nargs="+",
        default=["/", "/admin/login/"],
        help="One or more endpoint paths to benchmark",
    )
    parser.add_argument("--requests", type=int, default=120, help="Requests per path")
    parser.add_argument("--warmup", type=int, default=20, help="Warmup requests per path")
    parser.add_argument("--timeout", type=float, default=15.0, help="Request timeout in seconds")

    args = parser.parse_args()

    print("\nBenchmark config")
    print(f"- Base URL: {args.base_url}")
    print(f"- Paths: {', '.join(args.paths)}")
    print(f"- Requests/path: {args.requests}")
    print(f"- Warmup/path: {args.warmup}")

    print("\n" + "Path".ljust(24) + " " + "Total".rjust(7) + " " + "Success".rjust(8) + " " + "Failures".rjust(8) + " " + "Mean(ms)".rjust(10) + " " + "P50(ms)".rjust(10) + " " + "P95(ms)".rjust(10) + " " + "Min(ms)".rjust(10) + " " + "Max(ms)".rjust(10))
    print("-" * 115)

    all_stats: list[RunStats] = []
    for path in args.paths:
        stats = run_benchmark(
            base_url=args.base_url,
            path=path,
            requests_count=args.requests,
            warmup_count=args.warmup,
            timeout_seconds=args.timeout,
        )
        all_stats.append(stats)
        print(format_row(stats))

    total_failures = sum(item.failures for item in all_stats)
    print("\nFailures:", total_failures)


if __name__ == "__main__":
    main()
