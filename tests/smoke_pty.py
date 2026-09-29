"""Launch the real editor in a pseudo-terminal, edit, undo, and quit (Linux only).

Exits non-zero if the editor crashes, hangs, or prints a traceback.
"""
from __future__ import annotations

import os
import pty
import select
import signal
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENTRY = os.path.join(ROOT, "src", "lightwrite.py")


def read_for(fd, seconds):
    out = b""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        ready, _, _ = select.select([fd], [], [], 0.05)
        if ready:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
    return out


def main():
    home = tempfile.mkdtemp(prefix="lightwrite-smoke-")
    env = dict(os.environ, HOME=home, TERM="xterm-256color",
               LIGHTWRITE_LANG="en", COLUMNS="100", LINES="30")
    pid, fd = pty.fork()
    if pid == 0:
        os.execvpe(sys.executable, [sys.executable, ENTRY], env)

    output = read_for(fd, 2.0)
    steps = [
        b"hello world",
        b"\r",
        b"second line",
        b"\x7f\x7f",
        b"\x1a",
        b"\x1a",
        b"\x11",
        b"y\r",
    ]
    for data in steps:
        os.write(fd, data)
        output += read_for(fd, 0.4)

    deadline = time.monotonic() + 5
    status = None
    while time.monotonic() < deadline:
        done, status = os.waitpid(pid, os.WNOHANG)
        if done:
            break
        output += read_for(fd, 0.2)
    else:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
        sys.stderr.write(output.decode("utf-8", "replace")[-4000:])
        sys.exit("editor did not exit after Ctrl+Q")

    text = output.decode("utf-8", "replace")
    if "Traceback" in text:
        sys.stderr.write(text[-4000:])
        sys.exit("editor printed a traceback")
    code = os.waitstatus_to_exitcode(status) if hasattr(
        os, "waitstatus_to_exitcode") else status >> 8
    if code != 0:
        sys.stderr.write(text[-4000:])
        sys.exit("editor exited with %d" % code)
    print("smoke ok")


if __name__ == "__main__":
    main()
