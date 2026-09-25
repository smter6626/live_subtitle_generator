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
from uuid import uuid4

from settings import write_config_json


TRANSCRIPT_LINE_RE = re.compile(
    r"^\[(?P<start>\d+(?:\.\d+)?)s\s*->\s*"
    r"(?P<end>\d+(?:\.\d+)?)s\]\s*(?P<text>.*)$"
)


class CleanRenameError(ValueError):
    """A rejected Clean filename or unsafe source/destination."""


class CleanRenameVerificationError(CleanRenameError):
    """The rename committed, but its destination could not be verified."""

    def __init__(self, destination: Path, verified_path: Path | None):
        super().__init__("rename_outcome_ambiguous")
        self.destination = destination
        self.verified_path = verified_path


class CleanPathUnavailableError(CleanRenameError):
    """The writer has no regular .txt path in a fully verified Session directory."""

    def __init__(self, path_hint: Path | None):
        super().__init__("source_unavailable")
        self.path_hint = path_hint


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
        self._clean_path_hint = self.clean_path
        self.log_path = self.session_dir / "session.log"
        self.config_path = self.session_dir / "config.json"

        self._raw_file = open(self.raw_path, "w", encoding="utf-8", buffering=1)
        self._clean_file = open(self.clean_path, "w+", encoding="utf-8", buffering=1)
        clean_stat = os.fstat(self._clean_file.fileno())
        self._clean_identity = (clean_stat.st_dev, clean_stat.st_ino)
        self._log_file = open(self.log_path, "w", encoding="utf-8", buffering=1)

        self.raw_lines = 0
        self.clean_lines = 0
        self.closed = False
        self._clean_lock = threading.RLock()
        self._clean_snapshot = None

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

    def _open_verified_session_dir(self) -> int:
        try:
            directory_stat = self.session_dir.lstat()
            if not stat.S_ISDIR(directory_stat.st_mode) or (
                directory_stat.st_dev, directory_stat.st_ino
            ) != self._session_identity:
                raise CleanRenameError("source_unsafe")
            flags = (
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            dir_fd = os.open(self.session_dir, flags)
        except FileNotFoundError as exc:
            raise CleanRenameError("source_missing") from exc
        except CleanRenameError:
            raise
        except OSError as exc:
            raise CleanRenameError("source_unverified") from exc
        try:
            opened_stat = os.fstat(dir_fd)
            if (opened_stat.st_dev, opened_stat.st_ino) != self._session_identity:
                raise CleanRenameError("source_unsafe")
            return dir_fd
        except BaseException:
            try:
                os.close(dir_fd)
            except OSError:
                pass
            raise

    @staticmethod
    def _read_exact_fd(fd: int, expected_size: int) -> bytes:
        chunks = []
        offset = 0
        while offset < expected_size:
            chunk = os.pread(fd, min(1024 * 1024, expected_size - offset), offset)
            if not chunk:
                raise OSError(errno.EIO, "short read while capturing Clean history")
            chunks.append(chunk)
            offset += len(chunk)
        return b"".join(chunks)

    def _snapshot_clean_locked(self) -> bytes:
        if self.closed:
            if self._clean_snapshot is None:
                raise CleanRenameError("source_unverified")
            return self._clean_snapshot
        try:
            self._clean_file.flush()
            file_stat = os.fstat(self._clean_file.fileno())
            snapshot = self._read_exact_fd(self._clean_file.fileno(), file_stat.st_size)
        except (OSError, ValueError) as exc:
            raise CleanRenameError("source_unverified") from exc
        self._clean_snapshot = snapshot
        return snapshot

    def verified_clean_path(self, preferred: Path | None = None) -> Path:
        """Find a Session-local regular path for the open Clean writer's inode."""
        with self._clean_lock:
            try:
                dir_fd = self._open_verified_session_dir()
                with os.scandir(dir_fd) as entries:
                    for entry in entries:
                        if not entry.name.endswith(".txt"):
                            continue
                        try:
                            file_stat = entry.stat(follow_symlinks=False)
                        except OSError as exc:
                            raise CleanRenameError("source_unverified") from exc
                        if stat.S_ISREG(file_stat.st_mode) and (
                            file_stat.st_dev, file_stat.st_ino
                        ) == self._clean_identity:
                            current_dir = self.session_dir.lstat()
                            if not stat.S_ISDIR(current_dir.st_mode) or (
                                current_dir.st_dev, current_dir.st_ino
                            ) != self._session_identity:
                                raise CleanRenameError("source_unsafe")
                            path = self.session_dir / entry.name
                            self.clean_path = path
                            self._clean_path_hint = path
                            return path
                current_dir = self.session_dir.lstat()
                if not stat.S_ISDIR(current_dir.st_mode) or (
                    current_dir.st_dev, current_dir.st_ino
                ) != self._session_identity:
                    raise CleanRenameError("source_unsafe")
                self._snapshot_clean_locked()
            except CleanRenameError:
                self.clean_path = None
                raise
            except OSError as exc:
                self.clean_path = None
                raise CleanRenameError("source_unverified") from exc
            finally:
                try:
                    os.close(dir_fd)
                except (OSError, UnboundLocalError):
                    pass
            hint = preferred or self.clean_path or self._clean_path_hint
            self.clean_path = None
            raise CleanPathUnavailableError(hint)

    def recover_clean(self, stem: str) -> Path:
        """Create a verified no-clobber copy and switch the active writer if needed."""
        stem = validate_clean_stem(stem)
        with self._clean_lock:
            try:
                self.verified_clean_path()
            except CleanPathUnavailableError:
                pass
            else:
                raise CleanRenameError("source_available")

            snapshot = self._snapshot_clean_locked()
            destination = self.session_dir / f"{stem}.txt"
            dir_fd = self._open_verified_session_dir()
            temp_name = f".clean-recovery-{uuid4().hex}.tmp"
            temp_path = self.session_dir / temp_name
            temp_fd = None
            new_fd = None
            new_file = None
            owned_identity = None
            published = False
            try:
                flags = (
                    os.O_RDWR
                    | os.O_CREAT
                    | os.O_EXCL
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0)
                )
                temp_fd = os.open(temp_name, flags, 0o600, dir_fd=dir_fd)
                owned_stat = os.fstat(temp_fd)
                owned_identity = (owned_stat.st_dev, owned_stat.st_ino)
                offset = 0
                while offset < len(snapshot):
                    written = os.write(temp_fd, snapshot[offset:])
                    if written <= 0:
                        raise OSError(errno.EIO, "short write during Clean recovery")
                    offset += written
                os.fsync(temp_fd)
                temp_stat = os.fstat(temp_fd)
                if temp_stat.st_size != len(snapshot) or self._read_exact_fd(
                    temp_fd, temp_stat.st_size
                ) != snapshot:
                    raise OSError(errno.EIO, "Clean recovery verification failed")

                _rename_noreplace(temp_path, destination, dir_fd)
                published = True
                os.fsync(dir_fd)

                if not self.closed:
                    open_flags = (
                        os.O_RDWR
                        | os.O_APPEND
                        | getattr(os, "O_NOFOLLOW", 0)
                        | getattr(os, "O_CLOEXEC", 0)
                    )
                    new_fd = os.open(destination.name, open_flags, dir_fd=dir_fd)
                    new_stat = os.fstat(new_fd)
                    if (
                        not stat.S_ISREG(new_stat.st_mode)
                        or (new_stat.st_dev, new_stat.st_ino) != owned_identity
                        or new_stat.st_size != len(snapshot)
                        or self._read_exact_fd(new_fd, new_stat.st_size) != snapshot
                    ):
                        raise OSError(errno.EIO, "Clean recovery switch verification failed")
                    new_file = os.fdopen(
                        new_fd, "a+", encoding="utf-8", buffering=1, newline=""
                    )
                    new_fd = None

                old_file = self._clean_file
                if new_file is not None:
                    self._clean_file = new_file
                self._clean_identity = owned_identity
                self.clean_path = destination
                self._clean_path_hint = destination
                self._clean_snapshot = snapshot
                if new_file is not None:
                    try:
                        old_file.close()
                    except OSError:
                        pass
                return destination
            except OSError as exc:
                if exc.errno == errno.EEXIST:
                    raise CleanRenameError("destination_exists") from exc
                raise
            finally:
                if new_file is not None and self._clean_file is not new_file:
                    try:
                        new_file.close()
                    except OSError:
                        pass
                elif new_fd is not None:
                    try:
                        os.close(new_fd)
                    except OSError:
                        pass
                if temp_fd is not None:
                    try:
                        os.close(temp_fd)
                    except OSError:
                        pass
                cleanup_name = destination.name if published and self.clean_path != destination else temp_name
                if owned_identity is not None:
                    try:
                        cleanup_stat = os.stat(
                            cleanup_name, dir_fd=dir_fd, follow_symlinks=False
                        )
                        if (cleanup_stat.st_dev, cleanup_stat.st_ino) == owned_identity:
                            os.unlink(cleanup_name, dir_fd=dir_fd)
                    except FileNotFoundError:
                        pass
                    except OSError:
                        pass
                try:
                    os.close(dir_fd)
                except OSError:
                    pass

    def rename_clean(self, stem: str) -> Path:
        stem = validate_clean_stem(stem)
        with self._clean_lock:
            source = self.verified_clean_path()
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
                verified_path = self.verified_clean_path(preferred=destination)
            except CleanRenameError as exc:
                raise CleanRenameVerificationError(destination, None) from exc
            if verified_path == destination:
                return destination
            raise CleanRenameVerificationError(destination, verified_path)

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._log_file.write(f"{timestamp} [{level}] {message}\n")
        self._log_file.flush()

    def close(self):
        with self._clean_lock:
            if self.closed:
                return
            self._clean_snapshot = self._snapshot_clean_locked()
            for file_handle in (self._raw_file, self._clean_file, self._log_file):
                file_handle.flush()
                file_handle.close()
            self.closed = True

    @staticmethod
    def _append_lines(file_handle, lines):
        for line in lines:
            file_handle.write(line.rstrip() + "\n")
