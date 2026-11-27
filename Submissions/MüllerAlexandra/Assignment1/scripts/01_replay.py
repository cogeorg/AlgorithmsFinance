#!/usr/bin/env python3
"""Replay one plain/gzip JSON Lines file and emit results plus final book."""

from limit_order_book.replay_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
