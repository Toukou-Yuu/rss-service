import shutil
import sqlite3
import tarfile
import tempfile
from pathlib import Path

from rss_service.settings import Settings


def create_backup(settings: Settings, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        db_backup = tmp_dir / "rss.sqlite3"
        _backup_sqlite(settings.db_path, db_backup)
        if settings.reports_dir.exists():
            shutil.copytree(settings.reports_dir, tmp_dir / "reports")
        if settings.config_dir.exists():
            shutil.copytree(settings.config_dir, tmp_dir / "config")
        with tarfile.open(output, "w:gz") as archive:
            archive.add(db_backup, arcname="rss.sqlite3")
            reports_path = tmp_dir / "reports"
            config_path = tmp_dir / "config"
            if reports_path.exists():
                archive.add(reports_path, arcname="reports")
            if config_path.exists():
                archive.add(config_path, arcname="config")
    return output


def restore_backup(settings: Settings, input_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        with tarfile.open(input_path, "r:gz") as archive:
            archive.extractall(tmp_dir)

        restored_db = tmp_dir / "rss.sqlite3"
        if restored_db.exists():
            settings.db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(restored_db, settings.db_path)

        restored_reports = tmp_dir / "reports"
        if restored_reports.exists():
            if settings.reports_dir.exists():
                shutil.rmtree(settings.reports_dir)
            shutil.copytree(restored_reports, settings.reports_dir)

        restored_config = tmp_dir / "config"
        if restored_config.exists():
            if settings.config_dir.exists():
                shutil.rmtree(settings.config_dir)
            shutil.copytree(restored_config, settings.config_dir)


def _backup_sqlite(source: Path, target: Path) -> None:
    if not source.exists():
        sqlite3.connect(target).close()
        return
    source_connection = sqlite3.connect(source)
    target_connection = sqlite3.connect(target)
    try:
        source_connection.backup(target_connection)
    finally:
        target_connection.close()
        source_connection.close()
