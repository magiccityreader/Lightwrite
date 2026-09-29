"""Drive the real editor in a pseudo-terminal and check what it draws (Linux).

Each scenario starts a fresh editor under a throwaway HOME, sends keystrokes,
and asserts against the rendered screen and the files written to disk. The
screen is reconstructed with pyte, so assertions see what a user would see
rather than the raw byte stream, which partial redraws make unreadable.

Requires pyte (test-only):  pip install pyte
Run directly:  python3 tests/smoke_pty.py [scenario ...]
"""
from __future__ import annotations

import fcntl
import os
import pty
import shutil
import signal
import struct
import sys
import select
import tempfile
import termios
import time

try:
    import pyte
except ImportError:
    sys.exit("smoke_pty.py needs pyte: pip install pyte")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENTRY = os.path.join(ROOT, "src", "lightwrite.py")

ROWS, COLS = 40, 100

# Control keys, as read_input_event() decodes them.
QUIT = b"\x11"
SAVE = b"\x13"
SAVE_AS = b"\x17"
BOLD = b"\x02"
UNDO = b"\x1a"
FIND = b"\x06"
REPLACE = b"\x12"
CHAPTERS = b"\x14"
HELP = b"\x07"
ABOUT = b"\x08"
PAGEBREAK = b"\x0b"
SELECT_ALL = b"\x01"
OPEN = b"\x0f"
NEW = b"\x0e"
ALIGN_CENTER = b"\x05"
ENTER = b"\r"
BACKSPACE = b"\x7f"
ESC = b"\x1b"
DOWN = b"\x1b[B"

RTF_TEMPLATE = "{\\rtf1\\ansi\\deff0 %s\\par}"


class Timeout(Exception):
    pass


def _exit_code(status):
    if hasattr(os, "waitstatus_to_exitcode"):
        return os.waitstatus_to_exitcode(status)
    return status >> 8


class Session:
    """A running editor attached to a pty, with its own HOME."""

    def __init__(self, argv_doc=None, files=None, env_extra=None):
        self.home = tempfile.mkdtemp(prefix="lightwrite-smoke-")
        self.docs = os.path.join(self.home, "lightwrite")
        os.makedirs(self.docs, exist_ok=True)
        for name, body in (files or {}).items():
            self.write_doc(name, body)

        env = dict(
            os.environ,
            HOME=self.home,
            TERM="xterm-256color",
            LINES=str(ROWS),
            COLUMNS=str(COLS),
            LIGHTWRITE_LANG="en",
        )
        env.pop("LIGHTWRITE_PROFILE", None)
        env.update(env_extra or {})

        argv = [sys.executable, ENTRY]
        if argv_doc:
            argv.append(self.doc_path(argv_doc))

        self.raw = b""
        self.exit_code = None
        self.screen = pyte.Screen(COLS, ROWS)
        self.stream = pyte.ByteStream(self.screen)

        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.execvpe(sys.executable, argv, env)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ,
                    struct.pack("HHHH", ROWS, COLS, 0, 0))
        self.drain(1.2)

    # -- plumbing ---------------------------------------------------------
    def drain(self, seconds):
        end = time.monotonic() + seconds
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                break
            ready, _, _ = select.select([self.fd], [], [], min(0.05,
                                                               remaining))
            if not ready:
                continue
            try:
                chunk = os.read(self.fd, 1 << 16)
            except OSError:
                break
            if not chunk:
                break
            self.raw += chunk
            self.stream.feed(chunk)
        return self.text

    @property
    def text(self):
        """The screen as a user would see it right now."""
        return "\n".join(self.screen.display)

    def send(self, *chunks, settle=0.1):
        for chunk in chunks:
            os.write(self.fd, chunk)
            self.drain(settle)
        return self.text

    def type(self, text, settle=0.1):
        return self.send(text.encode("utf-8"), settle=settle)

    def clear_prompt(self, count=40):
        """Empty a prompt field that may be pre-filled."""
        return self.send(BACKSPACE * count, settle=0.25)

    def alive(self):
        if self.exit_code is not None:
            return False
        try:
            done, status = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            self.exit_code = 0
            return False
        if done:
            self.exit_code = _exit_code(status)
            return False
        return True

    def wait_exit(self, seconds=6):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if not self.alive():
                return self.exit_code
            self.drain(0.2)
        raise Timeout("editor is still running")

    def quit_clean(self, discard=False):
        """Ctrl+Q, optionally confirming the unsaved-changes prompt."""
        self.send(QUIT)
        if discard:
            self.expect("(y/n)")
            self.send(b"y\r")
        code = self.wait_exit()
        if code != 0:
            raise AssertionError("editor exited with %d" % code)

    def kill(self):
        try:
            if self.alive():
                os.kill(self.pid, signal.SIGKILL)
                os.waitpid(self.pid, 0)
                self.exit_code = -9
        except (OSError, ChildProcessError):
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        shutil.rmtree(self.home, ignore_errors=True)

    # -- assertions -------------------------------------------------------
    def expect(self, needle, timeout=5):
        """Wait until the screen shows needle."""
        end = time.monotonic() + timeout
        while True:
            if needle in self.text:
                return self.text
            if time.monotonic() >= end or not self.alive():
                raise AssertionError("screen never showed %r" % needle)
            self.drain(0.1)

    def undo_until(self, predicate, description, limit=15):
        """Press Undo until the screen satisfies predicate."""
        for _ in range(limit):
            if predicate(self.text):
                return self.text
            self.send(UNDO, settle=0.08)
        raise AssertionError(
            "%d undos never produced %s" % (limit, description))

    def refuse(self, needle, settle=0.5):
        self.drain(settle)
        if needle in self.text:
            raise AssertionError("screen still shows %r" % needle)

    def expect_raw(self, needle):
        text = self.raw.decode("utf-8", "replace")
        if needle not in text:
            raise AssertionError("terminal output lacks %r" % needle)

    # -- files ------------------------------------------------------------
    def doc_path(self, name):
        return os.path.join(self.docs, name)

    def write_doc(self, name, body):
        with open(self.doc_path(name), "w", encoding="ascii") as f:
            f.write(body)

    def read_doc(self, name):
        with open(self.doc_path(name), "r", encoding="ascii",
                  errors="replace") as f:
            return f.read()

    def expect_in_doc(self, name, *needles):
        body = self.read_doc(name)
        for needle in needles:
            if needle not in body:
                raise AssertionError("%s lacks %r" % (name, needle))
        return body


# -- scenarios ------------------------------------------------------------
# Each takes a factory that builds (and registers for cleanup) a Session.

def scenario_type_undo_quit(new):
    """Typing, Enter, Backspace and Undo all survive a round trip."""
    s = new()
    s.type("hello world")
    s.expect("hello world")
    s.send(ENTER)
    s.type("second line")
    s.expect("second line")
    s.send(BACKSPACE, BACKSPACE)
    s.expect("second li")
    s.refuse("second line")
    s.send(UNDO, UNDO)                 # one step per deleted character
    s.expect("second line")
    s.undo_until(lambda text: "hello world" in text and "second" not in text,
                 "the second line to disappear while the first survives")
    s.quit_clean(discard=True)


def scenario_save_then_quit_without_prompt(new):
    """Ctrl+S names a new file, and saving clears the unsaved flag."""
    s = new()
    s.type("saved text")
    s.send(SAVE)
    s.expect("~/lightwrite")           # filename prompt
    s.type("note")
    s.send(ENTER)
    s.expect("Saved: note.rtf")
    body = s.expect_in_doc("note.rtf", "saved text")
    if not body.lstrip().startswith("{\\rtf"):
        raise AssertionError("saved file is not RTF")
    s.quit_clean()                     # no prompt: nothing is unsaved


def scenario_quit_prompt_can_be_declined(new):
    """Answering 'n' to the unsaved prompt keeps the editor open."""
    s = new()
    s.type("unsaved work")
    s.send(QUIT)
    s.expect("(y/n)")
    s.send(b"n\r")
    if not s.alive():
        raise AssertionError("editor quit after the prompt was declined")
    s.expect("unsaved work")
    s.quit_clean(discard=True)


def scenario_overwrite_prompt(new):
    """Saving onto an existing name asks before overwriting."""
    s = new(files={"dup.rtf": RTF_TEMPLATE % "original"})
    s.type("replacement")
    s.send(SAVE_AS)
    s.type("dup")
    s.send(ENTER)
    s.expect("Overwrite")
    s.send(b"y\r")
    s.expect("Saved: dup.rtf")
    s.expect_in_doc("dup.rtf", "replacement")
    s.quit_clean()


def scenario_overwrite_can_be_declined(new):
    """Answering 'n' leaves the existing file untouched."""
    s = new(files={"keep.rtf": RTF_TEMPLATE % "original"})
    s.type("replacement")
    s.send(SAVE_AS)
    s.type("keep")
    s.send(ENTER)
    s.expect("Overwrite")
    s.send(b"n\r")
    s.expect_in_doc("keep.rtf", "original")
    if "replacement" in s.read_doc("keep.rtf"):
        raise AssertionError("declined overwrite still wrote the file")
    s.quit_clean(discard=True)


def scenario_open_argv_file(new):
    """A file named on the command line loads into the editor."""
    s = new(files={"preload.rtf": RTF_TEMPLATE % "preloaded content"},
            argv_doc="preload.rtf")
    s.expect("preloaded content")
    s.quit_clean()                     # a freshly loaded doc is not dirty


def scenario_file_browser_cancel(new):
    """Ctrl+O lists documents; ESC backs out without losing the document."""
    s = new(files={"listed.rtf": RTF_TEMPLATE % "listed"})
    s.type("in progress")
    s.send(OPEN)
    s.expect("(y/n)")                  # discard-changes confirmation
    s.send(b"y\r")
    s.expect("listed.rtf")
    s.send(ESC)
    s.expect("in progress")            # document survived the cancel
    s.send(QUIT)
    s.expect("(y/n)")                  # and is still marked unsaved
    s.send(b"y\r")
    s.wait_exit()


def scenario_file_browser_opens_document(new):
    """Picking a file in the browser loads it."""
    s = new(files={"pickme.rtf": RTF_TEMPLATE % "browser loaded this"})
    s.send(OPEN)
    s.expect("pickme.rtf")
    s.send(DOWN)                       # the first entry is ".."
    s.send(ENTER)
    s.expect("browser loaded this")
    s.quit_clean()


def scenario_formatting_reaches_the_file(new):
    """Bold and centre survive a save as RTF control words."""
    s = new()
    s.type("styled line")
    s.send(SELECT_ALL, BOLD, ALIGN_CENTER)
    s.send(SAVE)
    s.type("fmt")
    s.send(ENTER)
    s.expect("Saved: fmt.rtf")
    s.expect_in_doc("fmt.rtf", "\\b", "\\qc")
    s.quit_clean()


def scenario_search(new):
    """Find reports how many matches it found."""
    s = new()
    s.type("alpha beta alpha")
    s.send(FIND)
    s.type("alpha")
    s.send(ENTER)
    s.expect("1/2")
    s.quit_clean(discard=True)


def scenario_replace_all(new):
    """Replace-all rewrites every match, and Undo puts them back."""
    s = new()
    s.type("alpha beta alpha")
    s.send(REPLACE)
    s.clear_prompt()                   # the find field may be pre-filled
    s.type("alpha")
    s.send(ENTER)
    s.expect("Replace with")
    s.clear_prompt()
    s.type("omega")
    s.send(ENTER)
    s.expect("2 replacements")
    s.expect("omega beta omega")
    s.send(UNDO)
    s.expect("alpha beta alpha")
    s.quit_clean(discard=True)


def scenario_modal_screens(new):
    """Help, About and the chapter map open and close cleanly."""
    s = new()
    s.type("chapter body")
    s.send(HELP)
    s.expect("MANUAL")
    s.send(ESC)
    s.send(ABOUT)
    s.expect("LIGHTWRITE")
    s.send(ESC)
    s.send(CHAPTERS)
    s.expect("Chapter map")
    s.send(ESC)
    s.expect("chapter body")
    s.quit_clean(discard=True)


def scenario_new_document_prompt(new):
    """Ctrl+N asks before discarding, then clears the document."""
    s = new()
    s.type("throwaway")
    s.send(NEW)
    s.expect("(y/n)")
    s.send(b"y\r")
    s.expect("New document")
    s.refuse("throwaway")
    s.type("fresh start")
    s.expect("fresh start")
    s.quit_clean(discard=True)


def scenario_page_break_and_long_document(new):
    """A page break plus enough lines to scroll does not break redraw."""
    s = new()
    s.send(PAGEBREAK)
    for i in range(40):
        s.type("line %d" % i, settle=0.02)
        s.send(ENTER, settle=0.02)
    s.expect("line 39")
    s.refuse("line 0 ")                # scrolled out of view
    s.send(SAVE)
    s.type("long")
    s.send(ENTER)
    s.expect("Saved: long.rtf")
    s.expect_in_doc("long.rtf", "line 39", "\\page")
    s.quit_clean()


def scenario_profile_output(new):
    """LIGHTWRITE_PROFILE=1 prints timing totals on exit."""
    s = new(env_extra={"LIGHTWRITE_PROFILE": "1"})
    s.type("profiled")
    s.quit_clean(discard=True)
    s.drain(0.4)
    s.expect_raw("LIGHTWRITE_PROFILE")
    s.expect_raw("redraw")


SCENARIOS = [
    ("type_undo_quit", scenario_type_undo_quit),
    ("save_then_quit", scenario_save_then_quit_without_prompt),
    ("quit_prompt_declined", scenario_quit_prompt_can_be_declined),
    ("overwrite_prompt", scenario_overwrite_prompt),
    ("overwrite_declined", scenario_overwrite_can_be_declined),
    ("open_argv_file", scenario_open_argv_file),
    ("browser_cancel", scenario_file_browser_cancel),
    ("browser_open", scenario_file_browser_opens_document),
    ("formatting", scenario_formatting_reaches_the_file),
    ("search", scenario_search),
    ("replace_all", scenario_replace_all),
    ("modal_screens", scenario_modal_screens),
    ("new_document", scenario_new_document_prompt),
    ("page_break_long_doc", scenario_page_break_and_long_document),
    ("profile_output", scenario_profile_output),
]


def run(name, func):
    sessions = []

    def new(**kwargs):
        session = Session(**kwargs)
        sessions.append(session)
        return session

    try:
        func(new)
    except Exception as exc:                       # noqa: BLE001
        print("FAIL %-22s %s: %s" % (name, type(exc).__name__, exc))
        if sessions:
            raw = sessions[-1].raw.decode("utf-8", "replace")
            if "Traceback" in raw:
                print("---- editor traceback ----")
                print(raw[raw.index("Traceback"):])
            else:
                print("---- screen ----")
                print(sessions[-1].text.rstrip())
        return False
    else:
        print("ok   %s" % name)
        return True
    finally:
        for session in sessions:
            if session.alive():
                print("     (killed an editor that was still running)")
            session.kill()


def main(argv):
    wanted = set(argv[1:])
    unknown = wanted - {name for name, _ in SCENARIOS}
    if unknown:
        sys.exit("unknown scenario(s): %s" % ", ".join(sorted(unknown)))
    selected = [s for s in SCENARIOS if not wanted or s[0] in wanted]
    failures = [name for name, func in selected if not run(name, func)]
    print("%d/%d scenarios passed"
          % (len(selected) - len(failures), len(selected)))
    if failures:
        sys.exit("failed: %s" % ", ".join(failures))


if __name__ == "__main__":
    main(sys.argv)
