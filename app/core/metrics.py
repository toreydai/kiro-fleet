"""轻量级进程指标；供容器监控或 Prometheus 抓取。"""

from __future__ import annotations

from collections import Counter
from threading import Lock


class Metrics:
    def __init__(self) -> None:
        self._requests: Counter[tuple[str, int]] = Counter()
        self._lock = Lock()

    def record_request(self, path: str, status: int) -> None:
        with self._lock:
            self._requests[(path, status)] += 1

    def render_prometheus(self) -> str:
        with self._lock:
            lines = [
                "# HELP kiro_fleet_http_requests_total HTTP requests handled",
                "# TYPE kiro_fleet_http_requests_total counter",
            ]
            lines.extend(
                f'kiro_fleet_http_requests_total{{path="{path}",status="{status}"}} {count}'
                for (path, status), count in sorted(self._requests.items())
            )
        return "\n".join(lines) + "\n"


metrics = Metrics()
