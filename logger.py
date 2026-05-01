from datetime import datetime, timedelta
from pathlib import Path

_CONSOLE_PREFIX = {"DEBUG": "[DBG]", "INFO": "[INF]", "SUCCESS": "[OK]", "ERROR": "[ERR]"}


class CheckinLogger:
    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent
        else:
            base_dir = Path(base_dir)

        self.base_dir = base_dir
        self.logs_dir = base_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        self.log_file = self.logs_dir / f"checkin_{today}.log"

    def debug(self, msg):
        self._write("DEBUG", msg)

    def info(self, msg):
        self._write("INFO", msg)

    def success(self, msg):
        self._write("SUCCESS", msg)

    def error(self, msg):
        self._write("ERROR", msg)

    def exception(self, exc, tb=""):
        msg = f"{type(exc).__name__}: {exc}"
        if tb:
            msg += f"\n{tb}"
        self._write("ERROR", msg)

    def _write(self, level, msg):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{_CONSOLE_PREFIX.get(level, '[???]')} {msg}")
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] [{level}] {msg}\n")
        except Exception as e:
            print(f"[ERR] 写入日志失败: {e}")


def clean_old_logs(base_dir: Path, days: int = 30):
    logs_dir = base_dir / "logs"
    if not logs_dir.exists():
        return
    cutoff = datetime.now() - timedelta(days=days)
    deleted = 0
    for f in logs_dir.iterdir():
        if not f.is_file() or not (f.name.startswith("checkin_") and f.name.endswith(".log")):
            continue
        try:
            date_str = f.name.replace("checkin_", "").replace(".log", "")
            if datetime.strptime(date_str, "%Y-%m-%d") < cutoff:
                f.unlink()
                deleted += 1
        except ValueError:
            continue
    if deleted:
        print(f"[INF] 清理完成，共删除 {deleted} 个旧日志文件")
