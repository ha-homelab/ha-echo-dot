"""Small dependency-free helpers shared by the reproducible training stages."""
from pathlib import Path
import hashlib
import json
import re

SOURCE = Path(__file__).resolve().parent
DEFAULT_CONFIG = SOURCE / "configs/privet-myshka.json"
CORE_REVISION = "a70bd740d4e79ee8a8bb3db843fe862b88d5d6b0"


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_config(path=DEFAULT_CONFIG):
    cfg = json.loads(Path(path).read_text())
    if cfg.get("schema_version") != 1:
        raise ValueError("Unsupported recipe schema")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", cfg["model_id"]):
        raise ValueError("Model ID must be a safe ASCII basename")
    if cfg["frames"] != 250 or cfg["feature_step_ms"] != 10:
        raise ValueError("This recorded recipe requires 250 frames and a 10 ms hop")
    if cfg["architecture"]["stride"] != 3:
        raise ValueError("This recorded recipe requires stride 3")
    if cfg["sliding_window_size"] != 5:
        raise ValueError("This recorded recipe requires a five-score sliding window")
    if not 0 < cfg["provisional_cutoff"] < 1:
        raise ValueError("Provisional cutoff must be between zero and one")
    if cfg["training"]["max_updates"] < 1 or cfg["training"]["validation_interval"] < 1:
        raise ValueError("Training budgets must be positive")
    budget = cfg["training"]
    if budget["early_stopping_patience"] < 1 or budget["cpu_threads"] < 1:
        raise ValueError("Patience and CPU thread count must be positive")
    if set(budget["batch"]) != {"positive", "hard_negative", "background", "librispeech"} or any(
        not isinstance(n, int) or isinstance(n, bool) or n < 1 for n in budget["batch"].values()
    ):
        raise ValueError("All four batch components must be positive integers")
    return cfg


def work_dir(value):
    path = Path(value).expanduser().resolve()
    if path == path.parent or path == Path.home() or path == SOURCE.parent or path == SOURCE or SOURCE in path.parents:
        raise ValueError("Use a separate work directory, preferably private/wakeword-runs/NAME")
    return path


def candidate_dir(work, name):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,95}", name):
        raise ValueError("Candidate must be a lowercase ASCII directory name, at most 96 characters")
    return work / "models" / name


def write_json(path, value, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    else:
        temporary = path.with_name(path.name + ".pending")
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary.replace(path)
