import re
from datetime import datetime
from pathlib import Path

from settings import write_config_json


TRANSCRIPT_LINE_RE = re.compile(
    r"^\[(?P<start>\d+(?:\.\d+)?)s\s*->\s*"
    r"(?P<end>\d+(?:\.\d+)?)s\]\s*(?P<text>.*)$"
)


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

        self.raw_path = self.session_dir / "raw.txt"
        self.clean_path = self.session_dir / "clean.txt"
        self.log_path = self.session_dir / "session.log"
        self.config_path = self.session_dir / "config.json"

        self._raw_file = open(self.raw_path, "w", encoding="utf-8", buffering=1)
        self._clean_file = open(self.clean_path, "w", encoding="utf-8", buffering=1)
        self._log_file = open(self.log_path, "w", encoding="utf-8", buffering=1)

        self.raw_lines = 0
        self.clean_lines = 0
        self.closed = False

    def write_config(self, config: dict):
        write_config_json(self.config_path, config)

    def append_raw(self, lines):
        self._append_lines(self._raw_file, lines)
        self.raw_lines += len(lines)
        self._raw_file.flush()

    def append_clean(self, lines):
        self._append_lines(self._clean_file, lines)
        self.clean_lines += len(lines)
        self._clean_file.flush()

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._log_file.write(f"{timestamp} [{level}] {message}\n")
        self._log_file.flush()

    def close(self):
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
