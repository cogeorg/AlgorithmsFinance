"""Run a worker in a child process and enforce the per-replay time limit from the parent.

The worker talks to the parent with messages on a pipe:
    ("unit_start", tag)            a unit (one replay) begins: the limit clock starts
    ("unit_done", tag, payload)    the unit ended in time
    any other tuple                data for the caller (kept in `messages`)
The parent measures wall-clock time per unit. When a unit exceeds `limit_s` it sends SIGUSR1; the
child's handler reports the `seq` of the event being processed (read from the call stack of the
replay loop, so the timed loop itself has no extra work) and exits. No value is extrapolated.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import signal
import time

CTX = mp.get_context("fork")


def _seq_from_stack(frame) -> int | None:
    """seq of the event `e` that a function named `_replay*` is processing, or None."""
    while frame is not None:
        if frame.f_code.co_name.startswith("_replay"):
            event = frame.f_locals.get("e")
            if isinstance(event, dict):
                seq = event.get("seq")
                return seq if isinstance(seq, int) else None
        frame = frame.f_back
    return None


def _child_main(conn, worker, args) -> None:
    def on_stop(signum, frame):
        conn.send(("stopped", _seq_from_stack(frame)))
        os._exit(0)

    signal.signal(signal.SIGUSR1, on_stop)
    try:
        worker(conn, *args)
        conn.send(("end",))
    except BaseException as exc:                      # report, never hide
        conn.send(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        conn.close()


def run_limited(worker, args: tuple, limit_s: float, grace_s: float = 15.0) -> dict:
    """Run `worker(conn, *args)` in a child. Returns a dict:
    messages (data and unit messages in order), outcome ('end' | 'stopped' | 'error'),
    stopped_tag, stopped_after_s, events_done (seq at the stop), error."""
    parent, child = CTX.Pipe()
    proc = CTX.Process(target=_child_main, args=(child, worker, args))
    proc.start()
    assert proc.pid is not None
    child.close()
    out = {"messages": [], "outcome": "end", "stopped_tag": None, "stopped_after_s": None,
           "events_done": None, "error": None}
    unit = None                                       # (tag, start time on the parent clock)
    try:
        while True:
            wait = 30.0 if unit is None else max(0.0, unit[1] + limit_s - time.monotonic())
            if parent.poll(wait):
                try:
                    msg = parent.recv()
                except EOFError:
                    out.update(outcome="error", error="child process ended without a report")
                    break
                kind = msg[0]
                if kind == "unit_start":
                    unit = (msg[1], time.monotonic())
                    out["messages"].append(msg)
                elif kind == "unit_done":
                    unit = None
                    out["messages"].append(msg)
                elif kind == "end":
                    break
                elif kind == "error":
                    out.update(outcome="error", error=msg[1])
                    break
                else:
                    out["messages"].append(msg)
            elif unit is not None and time.monotonic() >= unit[1] + limit_s:
                out.update(outcome="stopped", stopped_tag=unit[0],
                           stopped_after_s=time.monotonic() - unit[1])
                os.kill(proc.pid, signal.SIGUSR1)
                if parent.poll(grace_s):
                    try:
                        msg = parent.recv()
                        if msg[0] == "stopped":
                            out["events_done"] = msg[1]
                    except EOFError:
                        pass
                break
    finally:
        proc.join(timeout=5)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
        parent.close()
    return out
