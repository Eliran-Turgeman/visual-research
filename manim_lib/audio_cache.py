"""Validated media and atomic, process-serialized narration cache storage."""

from contextlib import contextmanager
import hashlib
import io
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Iterator
from uuid import uuid4
import warnings

import av
from mutagen.mp3 import (
    HeaderNotFoundError,
    MP3,
    MPEGFrame,
    XingHeader,
    XingHeaderError,
)


class InvalidAudioError(ValueError):
    """An audio asset is missing, damaged, or not a complete MP3."""


def validate_mp3(path: Path, expected: dict | None = None) -> dict[str, Any]:
    """Fully decode an MP3 and optionally check its committed fingerprint."""
    try:
        size = path.stat().st_size
        if not size:
            raise ValueError("empty file")
        digest = hashlib.sha256()
        with path.open("rb") as audio:
            for chunk in iter(lambda: audio.read(1024 * 1024), b""):
                digest.update(chunk)
        integrity = {"size": size, "sha256": digest.hexdigest()}
        if expected is not None and expected != integrity:
            raise ValueError("file does not match its completed-audio fingerprint")
        with path.open("rb") as audio:
            header = MP3(audio).info
            audio.seek(header.frame_offset)
            frame = MPEGFrame(audio)
            audio.seek(header.frame_offset + XingHeader.get_offset(frame))
            try:
                xing = XingHeader(audio)
            except XingHeaderError:
                pass
            else:
                if xing.bytes > size - header.frame_offset:
                    raise ValueError("truncated MP3 payload")
        with av.open(str(path)) as container:
            if container.format.name != "mp3" or len(container.streams.audio) != 1:
                raise ValueError("expected one MP3 audio stream")
            stream = container.streams.audio[0]
            stream.codec_context.options = {"err_detect": "explode"}
            duration = 0.0
            for packet in container.demux(stream):
                if packet.is_corrupt:
                    raise ValueError("corrupt audio packet")
                encoded = io.BytesIO(bytes(packet))
                while encoded.tell() < packet.size:
                    header = MPEGFrame(encoded)
                    if header.layer != 3 or encoded.tell() > packet.size:
                        raise ValueError("incomplete MP3 frame")
                for frame in packet.decode():
                    duration += frame.samples / frame.sample_rate
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("no decodable audio samples")
            if stream.duration is not None:
                declared = float(stream.duration * stream.time_base)
                # MP3 encoder delay/padding can account for two frames, not
                # a stream that ended substantially before its declared length.
                tolerance = max(0.06, 2304 / stream.codec_context.sample_rate)
                if duration + tolerance < declared:
                    raise ValueError("truncated audio stream")
        return integrity
    except (OSError, ValueError, HeaderNotFoundError, av.error.FFmpegError) as error:
        raise InvalidAudioError(f"Invalid narration MP3 {path}: {error}") from error


@contextmanager
def staged_file(destination: Path) -> Iterator[Path]:
    """Publish only a successfully completed same-directory file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(
        f".{destination.stem}.{uuid4().hex}.part{destination.suffix}"
    )
    try:
        with staging.open("xb"):
            pass
        yield staging
        with staging.open("r+b") as completed:
            os.fsync(completed.fileno())
        os.replace(staging, destination)
    finally:
        staging.unlink(missing_ok=True)


class AudioCache:
    """A lock shared by cooperating OpenRouter writers, including processes.

    The lock file is intentionally persistent: deleting it could let separate
    processes lock different files with the same name. OS locks are released
    automatically if a writer exits.
    """

    def __init__(self, directory: str | Path, filename: str, timeout: float):
        self.directory = Path(directory)
        self.metadata_path = self.directory / filename
        self.timeout = timeout

    @contextmanager
    def locked(self) -> Iterator["AudioCache"]:
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / ".openrouter-cache.lock").open("a+b") as lock:
            if os.name == "nt":
                import msvcrt

                if lock.seek(0, os.SEEK_END) == 0:
                    lock.write(b"\0")
                    lock.flush()

                def acquire():
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)

                def release():
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                def acquire():
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                def release():
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    acquire()
                    break
                except OSError as error:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            f"Timed out waiting for narration cache {self.directory}; "
                            "another render may still be generating audio. Retry or "
                            "increase cache_lock_timeout."
                        ) from error
                    time.sleep(min(0.05, max(0, deadline - time.monotonic())))
            try:
                yield self
            finally:
                release()

    def read(self) -> list:
        """Recover complete prefix records and preserve damaged JSON verbatim."""
        if not self.metadata_path.exists():
            return []
        raw = self.metadata_path.read_bytes()
        try:
            records = json.loads(raw)
            if not isinstance(records, list):
                raise ValueError("cache metadata must contain a JSON list")
            return records
        except (ValueError, UnicodeError):
            backup = self.metadata_path.with_name(
                f"{self.metadata_path.stem}.corrupt-{uuid4().hex}.json"
            )
            os.replace(self.metadata_path, backup)
            records = []
            text = raw.decode("utf-8", errors="replace").lstrip()
            decoder = json.JSONDecoder()
            if text.startswith("["):
                remainder = text[1:].lstrip()
                while remainder and not remainder.startswith("]"):
                    try:
                        record, end = decoder.raw_decode(remainder)
                    except ValueError:
                        break
                    records.append(record)
                    remainder = remainder[end:].lstrip()
                    if not remainder.startswith(","):
                        break
                    remainder = remainder[1:].lstrip()
            self.write(records)
            warnings.warn(
                f"Recovered {len(records)} complete narration cache records; "
                f"damaged metadata preserved at {backup}.",
                RuntimeWarning,
                stacklevel=2,
            )
            return records

    def write(self, records: list) -> None:
        with staged_file(self.metadata_path) as staging:
            staging.write_text(
                json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    def upsert(self, records: list, data: dict) -> None:
        """Replace this request's duplicates without altering unrelated records."""
        self.write(
            [
                entry
                for entry in records
                if not isinstance(entry, dict)
                or entry.get("input_data") != data["input_data"]
            ]
            + [data]
        )
