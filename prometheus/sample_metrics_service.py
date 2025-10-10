"""샘플 Prometheus 메트릭 서버.

Incident Response Console 데모를 위해 http_error_rate / cpu_usage 지표를 주기적으로 갱신한다.
"""

from __future__ import annotations

import argparse
import random
import threading
import time
from typing import Tuple

from prometheus_client import Counter, Gauge, start_http_server

HTTP_ERROR_RATE = Gauge(
    "http_error_rate",
    "Fraction of HTTP requests returning 5xx in the last window",
)
CPU_USAGE = Gauge(
    "cpu_usage",
    "Synthetic CPU usage ratio (0-1)",
)
REQUEST_TOTAL = Counter(
    "sample_http_requests_total",
    "Synthetic HTTP request counter segmented by status code",
    ["status"],
)


_iteration = 0


def _next_window() -> Tuple[float, float]:
    """샘플링 회차에 따라 정상/이상 구간을 번갈아가며 반환한다."""

    global _iteration
    _iteration += 1

    if _iteration % 5 == 0:
        error_rate = random.uniform(0.08, 0.15)
        cpu = random.uniform(0.82, 0.95)
    else:
        error_rate = random.uniform(0.01, 0.035)
        cpu = random.uniform(0.35, 0.72)

    return error_rate, cpu


def _update_metrics(interval: float) -> None:
    while True:
        error_rate, cpu = _next_window()
        HTTP_ERROR_RATE.set(round(error_rate, 4))
        CPU_USAGE.set(round(cpu, 4))
        # 카운터도 함께 증가시켜 그래프 확인을 돕는다.
        ok = int((1 - error_rate) * 100)
        fail = int(error_rate * 100)
        if ok:
            REQUEST_TOTAL.labels(status="200").inc(ok)
        if fail:
            REQUEST_TOTAL.labels(status="500").inc(fail)
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample metrics feeder for Prometheus demos")
    parser.add_argument("--port", type=int, default=9001, help="HTTP port for metrics endpoint")
    parser.add_argument("--interval", type=float, default=5.0, help="Update interval in seconds")
    args = parser.parse_args()

    start_http_server(args.port)
    worker = threading.Thread(target=_update_metrics, args=(args.interval,), daemon=True)
    worker.start()

    print(f"Sample metrics server listening on http://127.0.0.1:{args.port}/metrics")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("Stopping sample metrics server...")


if __name__ == "__main__":
    main()
