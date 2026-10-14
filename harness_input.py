"""Typed input delivered to a running Claude Code session from another process.

`kb claude` (kb_cli/claude.py) runs `claude` inside a pseudo-terminal this module owns,
forwarding the user's own terminal to it unchanged, and listens on a Unix socket named by
the `claude` child's pid -- the same pid HarnessSession.register records, so any caller
holding a HarnessSession row can find the socket with no extra bookkeeping. A message sent
to the socket is written into the pseudo-terminal as a bracketed paste followed by Enter,
exactly what a user pasting and submitting it would produce, so the session receives it as
an ordinary user prompt.

A session started with plain `claude` has no socket and accepts no input this way; Linux
refuses to inject keystrokes into a terminal a process does not own (TIOCSTI is disabled
by default since kernel 6.2), which is why the wrapper has to own the pseudo-terminal."""

import collections
import errno
import fcntl
import json
import os
import pty
import re
import selectors
import signal
import socket
import sys
import termios
import time
import tty
from pathlib import Path
from typing import NamedTuple

SOCKET_DIR = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/kb-{os.getuid()}") / "kb" / "claude"

# Pauses that keep Claude Code from folding Enter, or the next message, into a paste; see _Typist.
_SUBMIT_DELAY_SECONDS = 0.15
_NEXT_MESSAGE_DELAY_SECONDS = 0.5
_PASTE_START = b"\x1b[200~"
_PASTE_END = b"\x1b[201~"
# Keys a caller may press by name. Escape interrupts a running turn or dismisses a permission
# dialog, but only with Claude Code's editor mode set to normal: in vim mode, Esc during a running
# tool only leaves insert mode (verified 2026-10-14, Claude Code 2.1.296).
KEYS = {"escape": b"\x1b"}
# Every C0 control except tab and newline, DEL, and every C1 control. Removing them keeps the
# message inert text: an embedded ESC[201~ would otherwise end the paste early and turn the
# rest of the message into raw keystrokes.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


class InputError(Exception):
    """A message could not be delivered; the text says why."""


def socket_path(pid: int) -> Path:
    return SOCKET_DIR / f"{pid}.sock"


def accepts_input(pid: int) -> bool:
    """Whether the session whose `claude` process is `pid` runs under `kb claude`."""
    return socket_path(pid).exists()


def clean(text: str) -> str:
    return _CONTROL_CHARS.sub("", text.replace("\r\n", "\n").replace("\r", "\n")).strip()


def send(pid: int, text: str) -> None:
    """Submit `text` as a prompt to the session whose `claude` process is `pid`."""
    _request(pid, {"text": text})


def send_key(pid: int, key: str) -> None:
    """Press `key` (a name in KEYS) in the session whose `claude` process is `pid`."""
    _request(pid, {"key": key})


def _request(pid: int, payload: dict[str, str]) -> None:
    path = socket_path(pid)
    if not path.exists():
        raise InputError("session was not started with `kb claude`")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(5)
            conn.connect(str(path))
            conn.sendall(json.dumps(payload).encode() + b"\n")
            reply = conn.makefile("rb").readline()
    except OSError as exc:
        raise InputError(f"session input socket unreachable: {exc}") from exc
    try:
        result = json.loads(reply)
    except ValueError as exc:
        raise InputError("session input socket sent no reply") from exc
    if not result.get("ok"):
        raise InputError(result.get("error") or "session refused the message")


def _write_all(fd: int, data: bytes) -> None:
    while data:
        data = data[os.write(fd, data) :]


def _copy_window_size(src_fd: int, dst_fd: int) -> None:
    try:
        size = fcntl.ioctl(src_fd, termios.TIOCGWINSZ, b"\0" * 8)
        fcntl.ioctl(dst_fd, termios.TIOCSWINSZ, size)
    except OSError:
        pass


class _Input(NamedTuple):
    data: bytes
    submit: bool  # press Enter after it


class _Typist:
    """Types queued input into the pseudo-terminal one item at a time: a message is pasted,
    then Enter, then a pause; a key is pressed, then a pause. Claude Code folds input that
    arrives right after a paste into that paste, so an Enter or a second message sent without
    the pauses merges into the previous message."""

    def __init__(self, master_fd: int) -> None:
        self.master_fd = master_fd
        self.queue: collections.deque[_Input] = collections.deque()
        self._submit_at: float | None = None
        self._next_paste_at = 0.0

    def seconds_until_due(self) -> float | None:
        if self._submit_at is not None:
            due = self._submit_at
        elif self.queue:
            due = self._next_paste_at
        else:
            return None
        return max(0.0, due - time.monotonic())

    def type_due(self) -> None:
        now = time.monotonic()
        if self._submit_at is not None and now >= self._submit_at:
            _write_all(self.master_fd, b"\r")
            self._submit_at = None
            self._next_paste_at = now + _NEXT_MESSAGE_DELAY_SECONDS
        if self._submit_at is None and self.queue and now >= self._next_paste_at:
            item = self.queue.popleft()
            _write_all(self.master_fd, item.data)
            if item.submit:
                self._submit_at = now + _SUBMIT_DELAY_SECONDS
            else:
                self._next_paste_at = now + _NEXT_MESSAGE_DELAY_SECONDS


def _read_request(conn: socket.socket) -> _Input | None:
    """The input a request asks for: {"text": ...} pastes and submits a message, {"key": NAME}
    presses one of KEYS. None for anything else, including a message empty once cleaned."""
    conn.settimeout(2)
    line = conn.makefile("rb").readline(1 << 20)
    try:
        request = json.loads(line)
        if "key" in request:
            return _Input(KEYS[request["key"]], submit=False)
        text = clean(str(request["text"]))
    except (ValueError, KeyError, TypeError):
        return None
    return _Input(_PASTE_START + text.encode() + _PASTE_END, submit=True) if text else None


def run(argv: list[str]) -> int:
    """Run `claude argv...` in a pseudo-terminal until it exits; return its exit status."""
    child_pid, master_fd = pty.fork()
    if child_pid == 0:
        try:
            os.execvp("claude", ["claude", *argv])
        finally:
            os._exit(127)

    stdin_fd, stdout_fd = sys.stdin.fileno(), sys.stdout.fileno()
    saved_attrs = termios.tcgetattr(stdin_fd) if os.isatty(stdin_fd) else None
    if saved_attrs is not None:
        _copy_window_size(stdin_fd, master_fd)
        signal.signal(signal.SIGWINCH, lambda *_: _copy_window_size(stdin_fd, master_fd))
        tty.setraw(stdin_fd)

    # Exit through the finally block below on a closed terminal or a kill, so the socket is removed.
    for signum in (signal.SIGHUP, signal.SIGTERM):
        signal.signal(signum, lambda signum, _frame: sys.exit(128 + signum))

    SOCKET_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = socket_path(child_pid)
    path.unlink(missing_ok=True)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    path.chmod(0o600)
    listener.listen()

    selector = selectors.DefaultSelector()
    selector.register(master_fd, selectors.EVENT_READ, "pty")
    selector.register(stdin_fd, selectors.EVENT_READ, "stdin")
    selector.register(listener, selectors.EVENT_READ, "socket")
    typist = _Typist(master_fd)
    try:
        while True:
            for key, _ in selector.select(typist.seconds_until_due()):
                if key.data == "pty":
                    try:
                        data = os.read(master_fd, 65536)
                    except OSError as exc:
                        if exc.errno != errno.EIO:
                            raise
                        data = b""
                    if not data:
                        return _exit_status(child_pid)
                    _write_all(stdout_fd, data)
                elif key.data == "stdin":
                    data = os.read(stdin_fd, 65536)
                    if data:
                        _write_all(master_fd, data)
                    else:
                        selector.unregister(stdin_fd)
                else:
                    conn, _ = listener.accept()
                    with conn:
                        item = _read_request(conn)
                        reply: dict[str, object]
                        if item:
                            typist.queue.append(item)
                            reply = {"ok": True}
                        else:
                            reply = {"ok": False, "error": "empty message or unknown key"}
                        try:
                            conn.sendall(json.dumps(reply).encode() + b"\n")
                        except OSError:
                            pass
            typist.type_due()
    finally:
        listener.close()
        path.unlink(missing_ok=True)
        if saved_attrs is not None:
            termios.tcsetattr(stdin_fd, termios.TCSAFLUSH, saved_attrs)


def _exit_status(pid: int) -> int:
    code = os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1])
    return code if code >= 0 else 128 - code
