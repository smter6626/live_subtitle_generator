import ctypes
import errno
import os
import re
import stat
import sys
import threading
import unicodedata
from datetime import datetime
from pathlib import Path

from settings import write_config_json


TRANSCRIPT_LINE_RE = re.compile(
    r"^\[(?P<start>\d+(?:\.\d+)?)s\s*->\s*"
    r"(?P<end>\d+(?:\.\d+)?)s\]\s*(?P<text>.*)$"
)


class CleanRenameError(ValueError):
    """A rejected Clean filename or unsafe source/destination."""


class CleanRenameVerificationError(CleanRenameError):
    """The rename committed, but its destination could not be verified."""

    def __init__(self, destination: Path):
        super().__init__("rename_outcome_ambiguous")
        self.destination = destination


def validate_clean_stem(stem: str) -> str:
    if not isinstance(stem, str) or not stem.strip():
        raise CleanRenameError("name_empty")
    if stem in (".", "..") or stem != stem.strip():
        raise CleanRenameError("name_invalid")
    if stem.lower().endswith(".txt"):
        raise CleanRenameError("name_suffix")
    if any(ch in stem for ch in ("/", "\\", ":")) or any(
        unicodedata.category(ch) == "Cc" for ch in stem
    ):
        raise CleanRenameError("name_invalid")
    return stem


def _rename_noreplace(source: Path, destination: Path, dir_fd: int):
    """Use an OS atomic, no-replace rename; never emulate it with a copy/link."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        function = getattr(libc, "renameatx_np", None)
        if function is None:
            raise CleanRenameError("rename_unavailable")
        function.argtypes = (
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint
        )
        function.restype = ctypes.c_int
        result = function(
            dir_fd, os.fsencode(source.name), dir_fd,
            os.fsencode(destination.name), 0x00000004,
        )
    elif sys.platform.startswith("linux"):
        function = getattr(libc, "renameat2", None)
        if function is None:
            raise CleanRenameError("rename_unavailable")
        function.argtypes = (
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint
        )
        function.restype = ctypes.c_int
        result = function(
            dir_fd, os.fsencode(source.name), dir_fd,
            os.fsencode(destination.name), 1,
        )
    else:
        raise CleanRenameError("rename_unavailable")
    if result:
        error = ctypes.get_errno()
        if error in (errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EINVAL):
            raise CleanRenameError("rename_unavailable")
        raise OSError(error, os.strerror(error), str(destination))


def session_id_from_time(start_time=None):
    start_time = start_time or datetime.now()
    return start_time.strftime("%Y-%m-%d_%H-%M-%S")


def format_transcript_time(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_runtime(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_transcript_line(line: str):
    match = TRANSCRIPT_LINE_RE.match(line.strip())
    if not match:
        return {
            "start": None,
            "end": None,
            "time": "",
            "range": "",
            "text": line.strip(),
        }

    start = float(match.group("start"))
    end = float(match.group("end"))
    text = match.group("text").strip()
    return {
        "start": start,
        "end": end,
        "time": format_transcript_time(start),
        "range": f"{start:.2f}s -> {end:.2f}s",
        "text": text,
    }


class TranscriptStore:
    def __init__(self, output_root: Path, session_id: str | None = None):
        self.output_root = Path(output_root)
        self.session_id = session_id or session_id_from_time()
        self.session_dir = self.output_root / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=False)
        session_stat = self.session_dir.stat()
        self._session_identity = (session_stat.st_dev, session_stat.st_ino)

        self.raw_path = self.session_dir / "raw.txt"
        self.clean_path = self.session_dir / "clean.txt"
        self.log_path = self.session_dir / "session.log"
        self.config_path = self.session_dir / "config.json"

        self._raw_file = open(self.raw_path, "w", encoding="utf-8", buffering=1)
        self._clean_file = open(self.clean_path, "w", encoding="utf-8", buffering=1)
        clean_stat = os.fstat(self._clean_file.fileno())
        self._clean_identity = (clean_stat.st_dev, clean_stat.st_ino)
        self._log_file = open(self.log_path, "w", encoding="utf-8", buffering=1)

        self.raw_lines = 0
        self.clean_lines = 0
        self.closed = False
        self._clean_lock = threading.RLock()

    def write_config(self, config: dict):
        write_config_json(self.config_path, config)

    def append_raw(self, lines):
        self._append_lines(self._raw_file, lines)
        self.raw_lines += len(lines)
        self._raw_file.flush()

    def append_clean(self, lines):
        with self._clean_lock:
            self._append_lines(self._clean_file, lines)
            self.clean_lines += len(lines)
            self._clean_file.flush()

    def rename_clean(self, stem: str) -> Path:
        stem = validate_clean_stem(stem)
        with self._clean_lock:
            source = self.clean_path
            destination = self.session_dir / f"{stem}.txt"
            if source.parent != self.session_dir or destination.parent != self.session_dir:
                raise CleanRenameError("name_invalid")
            try:
                directory_stat = self.session_dir.lstat()
            except FileNotFoundError as exc:
                raise CleanRenameError("source_missing") from exc
            if not stat.S_ISDIR(directory_stat.st_mode) or (
                directory_stat.st_dev, directory_stat.st_ino
            ) != self._session_identity:
                raise CleanRenameError("source_unsafe")
            try:
                source_stat = source.lstat()
            except FileNotFoundError as exc:
                raise CleanRenameError("source_missing") from exc
            if not stat.S_ISREG(source_stat.st_mode) or (
                source_stat.st_dev, source_stat.st_ino
            ) != self._clean_identity:
                raise CleanRenameError("source_unsafe")
            if destination == source:
                return source
            try:
                destination.lstat()
            except FileNotFoundError:
                pass
            else:
                raise CleanRenameError("destination_exists")
            try:
                flags = (
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_NOFOLLOW", 0)
                )
                dir_fd = os.open(self.session_dir, flags)
                try:
                    opened_stat = os.fstat(dir_fd)
                    if (opened_stat.st_dev, opened_stat.st_ino) != self._session_identity:
                        raise CleanRenameError("source_unsafe")
                    _rename_noreplace(source, destination, dir_fd)
                    self.clean_path = destination
                except BaseException:
                    try:
                        os.close(dir_fd)
                    except OSError:
                        pass  # Keep the failure that preceded the rename.
                    raise
                try:
                    os.close(dir_fd)
                except OSError:
                    pass  # The rename committed; reconcile the destination below.
            except OSError as exc:
                if exc.errno == errno.EEXIST:
                    raise CleanRenameError("destination_exists") from exc
                raise
            try:
                destination_stat = destination.lstat()
            except OSError as exc:
                verification_error = exc
            else:
                if stat.S_ISREG(destination_stat.st_mode) and (
                    destination_stat.st_dev, destination_stat.st_ino
                ) == self._clean_identity:
                    return destination
                verification_error = CleanRenameError("rename_outcome_ambiguous")
            try:
                source_stat = source.lstat()
            except OSError:
                pass
            else:
                if stat.S_ISREG(source_stat.st_mode) and (
                    source_stat.st_dev, source_stat.st_ino
                ) == self._clean_identity:
                    self.clean_path = source
                    raise CleanRenameError("rename_outcome_ambiguous") from verification_error
            raise CleanRenameVerificationError(destination) from verification_error

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._log_file.write(f"{timestamp} [{level}] {message}\n")
        self._log_file.flush()

    def close(self):
        with self._clean_lock:
            if self.closed:
                return
            for file_handle in (self._raw_file, self._clean_file, self._log_file):
                file_handle.flush()
                file_handle.close()
            self.closed = True

    @staticmethod
    def _append_lines(file_handle, lines):
        for line in lines:
            file_handle.write(line.rstrip() + "\n")
