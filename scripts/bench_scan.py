from __future__ import annotations

import statistics
import time
from pathlib import Path

from scriber.core.config import load_config
from scriber.scanner.scan import scan_project as scan_rust
from scriber.scanner.scan_py import scan_project as scan_python


def bench(name, fn, rounds=10):
    times = []
    for _ in range(rounds):
        start = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - start)

    print(f"{name}:")
    print(f"  files: {len(result)}")
    print(f"  min:   {min(times):.4f}s")
    print(f"  avg:   {statistics.mean(times):.4f}s")
    print(f"  p95:   {sorted(times)[int(len(times) * 0.95) - 1]:.4f}s")


def main():
    root = Path.cwd()
    config = load_config(root / "pyproject.toml")

    bench("python scan", lambda: scan_python(root, config))
    bench("rust scan", lambda: scan_rust(root, config))


if __name__ == "__main__":
    main()
