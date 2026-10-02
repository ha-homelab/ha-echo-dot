#!/usr/bin/env python3
"""Import deliberate, bounded real-voice WAV clips without opening a microphone.

Standard library only. Manifest paths are relative to WORK/recordings, not cwd.
The parent training pipeline can consume label, split, path, voice, and text.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import wave


SCHEMA_VERSION = 1
RATE = 16000
MAX_SECONDS = 30
SPLITS = {"train", "val", "test"}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")


def fail(message: str) -> None:
    raise ValueError(message)


def identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value) or value in {".", ".."}:
        fail("Speaker and session labels must be 1-80 ASCII letters, digits, '.', '_' or '-'.")
    return value


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_pcm(path: Path, max_seconds: float = MAX_SECONDS) -> bytes:
    if not path.is_file():
        fail(f"WAV file does not exist: {path}")
    with wave.open(str(path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, RATE, "NONE"):
            fail("Expected uncompressed mono 16 kHz PCM16 WAV; convert explicitly before import.")
        count = wav.getnframes()
        if count < 1 or count > int(max_seconds * RATE):
            fail(f"Clip duration must be greater than zero and no more than {max_seconds:g} seconds.")
        pcm = wav.readframes(count + 1)
        if len(pcm) != count * 2:
            fail("WAV frame count does not match its PCM payload.")
    return pcm


def read_manifest(root: Path) -> list[dict]:
    path = root / "manifest.jsonl"
    if not path.exists():
        return []
    if path.is_symlink():
        fail("Refusing a symlinked recording manifest.")
    records = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    fail("Expected a JSON object.")
                records.append(record)
            except (ValueError, TypeError) as exc:
                fail(f"Invalid manifest line {line_number}: {exc}")
    return records


def check_records(records: list[dict], split_by: str) -> dict:
    sessions: dict[str, str] = {}
    speakers: dict[str, set[str]] = {}
    audio: dict[str, str] = {}
    ids: set[str] = set()
    counts = {split: {"positive": 0, "negative": 0} for split in sorted(SPLITS)}
    for record in records:
        if record.get("schema_version") != SCHEMA_VERSION or record.get("source_kind") != "real_recording":
            fail("Unsupported recording manifest schema or source kind.")
        speaker = identifier(record.get("speaker", ""))
        session = identifier(record.get("session", ""))
        split = record.get("split")
        if split not in SPLITS or type(record.get("label")) is not int or record["label"] not in {0, 1}:
            fail("Invalid split or binary label in recording manifest.")
        pcm_hash = record.get("pcm_sha256", "")
        file_hash = record.get("sha256", "")
        if not all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in (pcm_hash, file_hash)):
            fail("Invalid recording hash.")
        source_id = f"real-{pcm_hash}"
        if record.get("source_id") != source_id or record.get("id") != source_id:
            fail("Recording identity must be derived from its full PCM SHA256.")
        if source_id in ids:
            fail("Duplicate PCM audio in recording manifest.")
        ids.add(source_id)
        if record.get("path") != f"audio/{pcm_hash}.wav":
            fail("Recording path must match its content-derived identity.")
        if (record.get("sample_rate"), record.get("channels"), record.get("sample_width_bytes")) != (RATE, 1, 2):
            fail("Invalid recording sample format in manifest.")
        if record.get("voice") != speaker or record.get("text") != record.get("transcript"):
            fail("Recording pipeline aliases voice/text disagree with speaker/transcript.")
        if not isinstance(record.get("text"), str):
            fail("Recording transcript must be text.")
        # A session label identifies one acquisition session, including multiple people.
        # Reuse its label for that entire session, even when speakers differ.
        if session in sessions and sessions[session] != split:
            fail(f"Recording session {session!r} crosses dataset splits.")
        sessions[session] = split
        for digest in (pcm_hash, file_hash):
            if digest in audio and audio[digest] != split:
                fail("Identical audio crosses dataset splits.")
            audio[digest] = split
        speakers.setdefault(speaker, set()).add(split)
        counts[split]["positive" if record["label"] else "negative"] += 1
    overlap = {speaker: sorted(parts) for speaker, parts in sorted(speakers.items()) if len(parts) > 1}
    if split_by == "speaker" and overlap:
        fail("Speaker overlap is forbidden by --split-by speaker; use different speakers or session-based evaluation.")
    return {
        "schema_version": SCHEMA_VERSION,
        "clips": len(records),
        "counts": counts,
        "split_by": split_by,
        "speaker_overlap": overlap,
        "evaluation_scope": "known_speaker_sessions" if overlap else "speaker_disjoint_within_imported_recordings",
        "scope_note": "This check covers this manifest only; audit synthetic and other datasets separately.",
    }


def verify_files(root: Path, records: list[dict]) -> None:
    for record in records:
        path = root / record["path"]
        if path.is_symlink() or path.parent.is_symlink():
            fail("Refusing symlinked recording files or audio directory.")
        pcm = read_pcm(path)
        if sha256(pcm) != record["pcm_sha256"] or sha256(path.read_bytes()) != record["sha256"]:
            fail(f"Recording checksum mismatch: {record['source_id']}")
        if record.get("samples") != len(pcm) // 2 or record.get("duration") != len(pcm) / 2 / RATE:
            fail(f"Recording duration metadata mismatch: {record['source_id']}")


@contextmanager
def dataset_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink():
        fail("Refusing a symlinked recording directory.")
    lock = root / ".import.lock"
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        fail("Another import holds .import.lock. If a process crashed, verify it has exited before removing the lock.")
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def write_manifest(root: Path, records: list[dict]) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".manifest-", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, root / "manifest.jsonl")
    finally:
        Path(temporary).unlink(missing_ok=True)


def import_recording(args: argparse.Namespace) -> dict:
    speaker, session = identifier(args.speaker), identifier(args.session)
    pcm = read_pcm(args.wav.expanduser().resolve(), args.max_seconds)
    pcm_hash = sha256(pcm)
    root = args.work_dir.expanduser().resolve() / "recordings"
    with dataset_lock(root):
        records = read_manifest(root)
        check_records(records, args.split_by)
        verify_files(root, records)
        label = int(args.label == "positive")
        for record in records:
            if record["pcm_sha256"] == pcm_hash:
                expected = (speaker, session, args.split, label, args.transcript)
                actual = tuple(record[key] for key in ("speaker", "session", "split", "label", "transcript"))
                if actual != expected:
                    fail("This audio was already imported with different metadata; do not reuse it across splits or relabel it silently.")
                return {"status": "already_imported", "source_id": record["source_id"], "manifest": str(root / "manifest.jsonl"), **check_records(records, args.split_by)}
        record = {
            "schema_version": SCHEMA_VERSION,
            "id": f"real-{pcm_hash}",
            "source_id": f"real-{pcm_hash}",
            "source_kind": "real_recording",
            "path": f"audio/{pcm_hash}.wav",
            "speaker": speaker,
            "voice": speaker,
            "session": session,
            "split": args.split,
            "label": label,
            "transcript": args.transcript,
            "text": args.transcript,
            "pcm_sha256": pcm_hash,
            "sha256": "0" * 64,
            "sample_rate": RATE,
            "channels": 1,
            "sample_width_bytes": 2,
            "samples": len(pcm) // 2,
            "duration": len(pcm) / 2 / RATE,
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }
        # Check split policy before creating any audio artifact.
        check_records(records + [record], args.split_by)
        audio_dir = root / "audio"
        audio_dir.mkdir(exist_ok=True, mode=0o700)
        if audio_dir.is_symlink():
            fail("Refusing a symlinked audio directory.")
        fd, temporary = tempfile.mkstemp(prefix=".recording-", suffix=".wav", dir=audio_dir)
        try:
            with os.fdopen(fd, "wb") as stream:
                with wave.open(stream, "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(RATE)
                    wav.writeframes(pcm)
                stream.flush()
                os.fsync(stream.fileno())
            record["sha256"] = sha256(Path(temporary).read_bytes())
            target = root / record["path"]
            if target.exists() or target.is_symlink():
                fail("An unindexed audio file already occupies the destination; inspect it before retrying.")
            os.replace(temporary, target)
            try:
                write_manifest(root, records + [record])
            except BaseException:
                target.unlink(missing_ok=True)
                raise
        finally:
            Path(temporary).unlink(missing_ok=True)
        return {"status": "imported", "source_id": record["source_id"], "manifest": str(root / "manifest.jsonl"), "path_base": str(root), **check_records(records + [record], args.split_by)}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for name, help_text in (("import", "Import one deliberately recorded WAV clip."), ("check", "Verify every recording, hash and split boundary.")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--work-dir", type=Path, required=True, help="Private training work directory.")
        command.add_argument("--split-by", choices=("session", "speaker"), default="session", help="Session separation is mandatory. Speaker adds a stricter disjoint-speaker check.")
        if name == "import":
            command.add_argument("--wav", type=Path, required=True, help="Existing mono 16 kHz PCM16 WAV; no microphone is opened.")
            command.add_argument("--speaker", required=True, help="Pseudonymous speaker label.")
            command.add_argument("--session", required=True, help="Globally unique recording-session label; all clips from one session stay in one split.")
            command.add_argument("--split", choices=sorted(SPLITS), required=True)
            command.add_argument("--label", choices=("positive", "negative"), required=True)
            command.add_argument("--transcript", default="", help="Words actually spoken; empty is allowed for non-speech negatives.")
            command.add_argument("--max-seconds", type=float, default=MAX_SECONDS, help="Per-clip upper duration bound, no more than 30 seconds (default: 30).")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "import":
            if not 0 < args.max_seconds <= MAX_SECONDS:
                fail("--max-seconds must be greater than zero and at most 30.")
            if args.label == "positive" and not args.transcript.strip():
                fail("Positive recordings require the words actually spoken in --transcript.")
            summary = import_recording(args)
        else:
            root = args.work_dir.expanduser().resolve() / "recordings"
            if not (root / "manifest.jsonl").is_file():
                fail("No recording manifest exists in this work directory.")
            records = read_manifest(root)
            summary = check_records(records, args.split_by)
            verify_files(root, records)
            summary.update(status="verified", manifest=str(root / "manifest.jsonl"), path_base=str(root))
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, wave.Error, EOFError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
