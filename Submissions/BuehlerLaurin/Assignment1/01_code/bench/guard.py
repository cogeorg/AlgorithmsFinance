"""Parent-process phase watchdog; no watchdog work inside timed engine loops."""
import json
import queue
import subprocess
import threading
import time


def run_phased(cmd, timeout_s):
    start = time.perf_counter()
    process = subprocess.Popen(list(cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace",
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    lines = queue.Queue()
    def read():
        for line in process.stdout:
            lines.put(line)
        lines.put(None)
    threading.Thread(target=read, daemon=True).start()
    phase, stopped, tail = "startup", None, []
    deadline = time.perf_counter() + max(30.0, timeout_s)
    while True:
        now = time.perf_counter()
        if now >= deadline:
            stopped = phase
            process.kill()
            break
        try:
            line = lines.get(timeout=min(0.05, max(0.001, deadline - now)))
        except queue.Empty:
            continue
        if line is None:
            break
        tail.append(line)
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if "bench_phase" in event:
            if event["action"] == "start":
                phase = event["bench_phase"]
                deadline = time.perf_counter() + timeout_s
            else:
                phase = "between_phases"
                deadline = time.perf_counter() + max(30.0, timeout_s)
    process.wait()
    return {"status": "stopped" if stopped or process.returncode == 124 else
            ("ok" if process.returncode == 0 else f"error({process.returncode})"),
            "stopped_phase": stopped or "", "wall_s": time.perf_counter() - start,
            "limit_s": timeout_s, "cmd": " ".join(cmd), "log_tail": "".join(tail)[-4000:]}
