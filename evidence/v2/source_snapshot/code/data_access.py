"""Prepare small, reproducible subsets of the official OpenEarthMap archive.

Only the ZIP directory and requested members are transferred. The publisher's
archive MD5 identifies the source; it is NOT claimed to be verified without
downloading the entire archive. Extracted members have locally computed SHA256.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import random
import queue
import re
import shutil
import stat
import sys
import tempfile
import threading
import time
import zipfile
import zlib

import requests
from urllib3.exceptions import HTTPError as TransportError


SOURCE_URL = "https://zenodo.org/records/7223446/files/OpenEarthMap.zip"
SOURCE_MD5 = "64155d1dc9d3b68536063f79878e1a67"
CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+)\Z")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_PROJECT_BYTES = 2_000_000_000
# Internal data allocation; the user's total project cap remains 2 GB.
MAX_DATA_BYTES = 700_000_000


class RangeDownloadError(RuntimeError):
    """The remote archive cannot safely be accessed by byte ranges."""


class HTTPRangeReader(io.RawIOBase):
    """Seekable, bounded-memory HTTP file, requiring validated 206 responses."""

    def __init__(self, url=SOURCE_URL, block_size=1024 * 1024, cache_blocks=8):
        super().__init__()
        if block_size <= 0 or cache_blocks <= 0:
            raise ValueError("block_size and cache_blocks must be positive")
        self.url = url
        self.block_size = block_size
        self.cache_blocks = cache_blocks
        self.session = requests.Session()
        self.position = 0
        self.size = None
        self.bytes_transferred = 0
        self.requests_made = 0
        self.cache = OrderedDict()
        try:
            start, end, total, data = self._request("bytes=-65536")
            if end != total - 1 or len(data) != min(65536, total):
                raise RangeDownloadError("Server returned an incorrect suffix range")
            self.size = total
            self.tail_start = start
            self.tail = data
        except Exception:
            self.session.close()
            raise

    def _request(self, range_header):
        for attempt in range(3):
            response = None
            try:
                self.requests_made += 1
                response = self.session.get(
                    self.url,
                    headers={"Range": range_header, "Accept-Encoding": "identity"},
                    stream=True,
                    timeout=(20, 60),
                )
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    delay = 2 ** attempt
                    if response.status_code == 429:
                        try:
                            delay = max(delay, min(60, float(response.headers.get("Retry-After", "1"))))
                        except ValueError:
                            pass
                    response.close()
                    time.sleep(delay)
                    continue
                if response.status_code != 206:
                    raise RangeDownloadError(
                        f"HTTP {response.status_code}: server must support Range with "
                        "206 Partial Content; full-archive download refused"
                    )
                match = CONTENT_RANGE.fullmatch(response.headers.get("Content-Range", ""))
                if match is None:
                    raise RangeDownloadError("Missing or malformed Content-Range")
                start, end, total = map(int, match.groups())
                if not (0 <= start <= end < total):
                    raise RangeDownloadError("Invalid Content-Range bounds")
                if self.size is not None and total != self.size:
                    raise RangeDownloadError("Archive size changed during transfer")
                if range_header.startswith("bytes=-"):
                    expected_start = max(0, total - int(range_header[7:]))
                    expected_end = total - 1
                else:
                    expected_start, expected_end = map(int, range_header[6:].split("-"))
                if (start, end) != (expected_start, expected_end):
                    raise RangeDownloadError(
                        f"Incorrect Content-Range: requested {range_header}, "
                        f"received {response.headers['Content-Range']}"
                    )
                if response.headers.get("Content-Encoding", "identity") != "identity":
                    raise RangeDownloadError("Encoded range responses are not supported")
                expected_length = end - start + 1
                declared = response.headers.get("Content-Length")
                if declared is not None and int(declared) != expected_length:
                    raise RangeDownloadError("Content-Length disagrees with Content-Range")
                data = response.raw.read(expected_length + 1)
                self.bytes_transferred += len(data)
                if len(data) != expected_length:
                    raise RangeDownloadError("Truncated or oversized range response")
                return start, end, total, data
            except (requests.RequestException, TransportError, OSError) as exc:
                if attempt == 2:
                    raise RangeDownloadError(f"Range request failed: {exc}") from exc
                time.sleep(2 ** attempt)
            finally:
                if response is not None:
                    response.close()
        raise RangeDownloadError("Range request failed")

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        self._checkClosed()
        if whence == io.SEEK_SET:
            new_position = offset
        elif whence == io.SEEK_CUR:
            new_position = self.position + offset
        elif whence == io.SEEK_END:
            new_position = self.size + offset
        else:
            raise ValueError("Invalid whence")
        if new_position < 0:
            raise ValueError("Negative seek")
        self.position = new_position
        return self.position

    def read(self, size=-1):
        self._checkClosed()
        remaining = max(0, self.size - self.position)
        size = remaining if size is None or size < 0 else min(size, remaining)
        # zipfile uses bounded reads. Protect accidental archive-wide reads.
        if size > 128 * 1024 * 1024:
            raise RangeDownloadError("Single read exceeds 128 MiB; refusing large transfer")
        pieces = []
        while size:
            if self.position >= self.tail_start:
                piece = self.tail[self.position - self.tail_start:self.position - self.tail_start + size]
            else:
                block = self.position // self.block_size
                if block not in self.cache:
                    start = block * self.block_size
                    end = min(start + self.block_size, self.size) - 1
                    _, _, _, data = self._request(f"bytes={start}-{end}")
                    self.cache[block] = data
                    if len(self.cache) > self.cache_blocks:
                        self.cache.popitem(last=False)
                self.cache.move_to_end(block)
                offset = self.position - block * self.block_size
                piece = self.cache[block][offset:offset + size]
            if not piece:
                raise RangeDownloadError("Range reader made no progress")
            pieces.append(piece)
            self.position += len(piece)
            size -= len(piece)
        return b"".join(pieces)

    def close(self):
        self.session.close()
        super().close()


def safe_member_path(name):
    """Reject platform-dependent traversal, absolute paths and drive names."""
    path = PurePosixPath(name)
    if (not name or "\\" in name or path.is_absolute() or
            any(part in ("", ".", "..") or ":" in part or part.endswith((".", " "))
                for part in name.split("/"))):
        raise ValueError(f"Unsafe ZIP member path: {name!r}")
    return path


def discover_pairs(archive):
    """Return region -> image/label pairs, matched by relative filename."""
    groups = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        path = safe_member_path(info.filename)
        if stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError(f"Symbolic link ZIP member refused: {info.filename}")
        parts = path.parts
        indices = [i for i, part in enumerate(parts) if part in ("images", "labels")]
        if len(indices) != 1 or indices[0] < 1:
            continue
        index = indices[0]
        if path.suffix.lower() not in (".tif", ".tiff", ".png", ".jpg", ".jpeg"):
            continue
        region = parts[index - 1]
        kind = parts[index]
        relative = str(PurePosixPath(*parts[index + 1:]))
        bucket = groups.setdefault(region, {"images": {}, "labels": {}})[kind]
        if relative in bucket:
            raise ValueError(f"Ambiguous duplicate member for {region}/{kind}/{relative}")
        bucket[relative] = info
    result = {}
    for region, kinds in groups.items():
        names = sorted(kinds["images"].keys() & kinds["labels"].keys())
        if names:
            result[region] = [(kinds["images"][name], kinds["labels"][name]) for name in names]
    if not result:
        raise ValueError("No complete region/images and region/labels pairs found")
    return dict(sorted(result.items()))


def extract_member(archive, info, output):
    path = safe_member_path(info.filename)
    root = output.resolve()
    destination = root.joinpath(*path.parts)
    # Resolve existing symlink/junction components before opening output.
    if not destination.resolve().is_relative_to(root):
        raise ValueError(f"ZIP member escapes output directory: {info.filename}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {destination}")
    temporary = None
    digest = hashlib.sha256()
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=destination.parent,
                                         prefix=destination.name + ".", suffix=".part",
                                         delete=False) as target:
            temporary = Path(target.name)
            with archive.open(info) as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                    target.write(chunk)
        temporary.replace(destination)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise
    return {"member": info.filename, "relative_path": path.as_posix(),
            "bytes": info.file_size, "compressed_bytes": info.compress_size,
            "zip_crc32": f"{info.CRC:08x}", "sha256": digest.hexdigest()}


def directory_bytes(directory):
    return sum(path.stat().st_size for path in directory.rglob("*")
               if path.is_file() and not path.is_symlink()) if directory.exists() else 0


def select_pairs(pairs, regions, limit, seed=None):
    """Selection uses filenames alone; each region has an independent RNG."""
    selected = []
    for region in sorted(set(regions)):
        candidates = pairs[region]
        if seed is None:
            chosen = candidates[:limit]
        else:
            chosen = random.Random(f"{seed}:{region}").sample(candidates, min(limit, len(candidates)))
            chosen.sort(key=lambda pair: pair[0].filename)
        selected.extend((region, pair) for pair in chosen)
    return selected


def verify_existing(info, record, output):
    """Trust resume progress only after checking member identity, size and SHA."""
    if record.get("member") != info.filename or record.get("relative_path") != info.filename:
        raise ValueError(f"Resume member mismatch: {info.filename}")
    path = output.joinpath(*safe_member_path(info.filename).parts)
    if not path.resolve().is_relative_to(output.resolve()) or not path.is_file():
        raise ValueError(f"Resume file missing or unsafe: {info.filename}")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if path.stat().st_size != info.file_size or digest.hexdigest() != record.get("sha256"):
        raise ValueError(f"Resume SHA256/size mismatch: {info.filename}")


def recover_existing(info, output):
    """Recover a completed atomic rename interrupted before its manifest save."""
    path = output.joinpath(*safe_member_path(info.filename).parts)
    if not path.resolve().is_relative_to(output.resolve()) or not path.is_file():
        raise ValueError(f"Untracked file is unsafe: {info.filename}")
    digest = hashlib.sha256()
    crc = 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
            crc = zlib.crc32(chunk, crc)
    if path.stat().st_size != info.file_size or crc != info.CRC:
        raise ValueError(f"Untracked file does not match ZIP CRC/size: {info.filename}")
    return {"member": info.filename, "relative_path": info.filename,
            "bytes": info.file_size, "compressed_bytes": info.compress_size,
            "zip_crc32": f"{info.CRC:08x}", "sha256": digest.hexdigest(),
            "recovered_before_manifest_save": True}


def prepare(regions, limit, output, list_only=False, plan_only=False, seed=None, workers=1):
    started = time.monotonic()
    with HTTPRangeReader() as remote, zipfile.ZipFile(remote) as archive:
        pairs = discover_pairs(archive)
        if list_only:
            for region, region_pairs in pairs.items():
                print(f"{region}\t{len(region_pairs)}")
            print(f"Regions: {len(pairs)}; complete pairs: {sum(map(len, pairs.values()))}; "
                  f"transferred: {remote.bytes_transferred:,} bytes; "
                  f"elapsed: {time.monotonic() - started:.2f}s", file=sys.stderr)
            return
        unknown = sorted(set(regions) - pairs.keys())
        if unknown:
            raise ValueError(f"Unknown regions: {', '.join(unknown)}; use --list")
        selected = select_pairs(pairs, regions, limit, seed)
        selection = {"regions": sorted(set(regions)), "limit_per_region": limit,
                     "seed": seed,
                     "ordering": ("lexicographic member relative filename" if seed is None else
                                  "random.Random(str(seed)+':' + region).sample; sort chosen members lexicographically"),
                     "selection_uses_image_or_label_content": False}
        planned_pairs = [{"region": region, "rgb_member": rgb.filename, "label_member": label.filename}
                         for region, (rgb, label) in selected]
        required = sum(info.file_size for _, pair in selected for info in pair)
        if plan_only:
            print(json.dumps({
                "source_url": SOURCE_URL, "archive_bytes": remote.size,
                "regions_available": {name: len(items) for name, items in pairs.items()},
                "limit_per_region": limit, "selected_pairs": len(selected),
                "selection": selection, "planned_pairs": planned_pairs,
                "extracted_bytes": required,
                "compressed_member_bytes": sum(info.compress_size for _, pair in selected for info in pair),
                "regions": {region: {"pairs": min(limit, len(pairs[region])),
                                      "extracted_bytes": sum(info.file_size for selected_region, pair in selected
                                                             if selected_region == region for info in pair)}
                            for region in sorted(set(regions))},
                "image_payload_downloaded": False,
                "directory_transfer_bytes": remote.bytes_transferred,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }, indent=2))
            return
        output_resolved = output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        manifest_path = output / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (manifest.get("source_url") != SOURCE_URL or manifest.get("archive_bytes") != remote.size or
                    manifest.get("selection") != selection or manifest.get("planned_pairs") != planned_pairs):
                raise ValueError("Existing manifest selection/source differs; use matching --regions/--limit/--seed or a new output")
            manifest.setdefault("attempts", []).append(manifest.get("transfer", {}))
        else:
            manifest = {
                "dataset": "OpenEarthMap", "source_url": SOURCE_URL,
                "publisher_archive_md5": SOURCE_MD5, "archive_md5_verified": False,
                "archive_bytes": remote.size, "created_utc": datetime.now(timezone.utc).isoformat(),
                "selection": selection, "planned_pairs": planned_pairs,
                "pairs": [], "attempts": [],
            }
        entries = {entry["rgb"]["member"]: entry for entry in manifest["pairs"]}
        remaining = 0
        for region, (rgb, label) in selected:
            entry = entries.get(rgb.filename, {"region": region})
            for kind, info in (("rgb", rgb), ("label", label)):
                if kind in entry:
                    verify_existing(info, entry[kind], output)
                elif output.joinpath(*safe_member_path(info.filename).parts).exists():
                    entry[kind] = recover_existing(info, output)
                else:
                    remaining += info.file_size
            if "rgb" in entry and rgb.filename not in entries:
                entries[rgb.filename] = entry
                manifest["pairs"].append(entry)
        data_root = PROJECT_ROOT / "data"
        data_existing = directory_bytes(data_root if output_resolved.is_relative_to(data_root.resolve()) else output)
        if data_existing + remaining + 256_000 > MAX_DATA_BYTES:
            raise OSError(f"Internal data quota exceeded: {data_existing + remaining:,} bytes would exceed {MAX_DATA_BYTES:,} bytes; reduce --limit")
        if output_resolved.is_relative_to(PROJECT_ROOT) and directory_bytes(PROJECT_ROOT) + remaining + 256_000 > MAX_PROJECT_BYTES:
            raise OSError("Project storage would exceed the 2,000,000,000-byte limit; reduce --limit")
        free = shutil.disk_usage(output).free
        if remaining + 256 * 1024 * 1024 > free:
            raise OSError(f"Insufficient disk space: need {remaining:,} bytes plus 256 MiB reserve")
        readers = [remote]
        progress_lock = threading.RLock()
        stop_workers = threading.Event()
        def save_manifest():
            # Caller holds progress_lock whenever concurrent workers are active.
            manifest["pairs"].sort(key=lambda entry: entry["rgb"]["member"])
            manifest["transfer"] = {"bytes": sum(reader.bytes_transferred for reader in readers),
                                    "requests": sum(reader.requests_made for reader in readers),
                                    "workers": workers,
                                    "elapsed_seconds": round(time.monotonic() - started, 3)}
            pending = output / "manifest.json.tmp"
            pending.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            pending.replace(manifest_path)
        manifest["status"] = "in_progress"
        manifest.pop("error", None)
        manifest.setdefault("region_progress", {})
        save_manifest()
        def run_pair(worker_archive, region, rgb, label):
            if stop_workers.is_set():
                return
            # A pair is owned by exactly one worker; manifest state is locked.
            for kind, info in (("rgb", rgb), ("label", label)):
                with progress_lock:
                    entry = entries.get(rgb.filename, {"region": region})
                    already_done = kind in entry
                if already_done:
                    continue
                record = extract_member(worker_archive, worker_archive.getinfo(info.filename), output)
                with progress_lock:
                    if rgb.filename not in entries:
                        entries[rgb.filename] = entry
                        manifest["pairs"].append(entry)
                    entry[kind] = record
                    save_manifest()
            with progress_lock:
                complete = sum(1 for entry in manifest["pairs"] if entry["region"] == region and "label" in entry)
                planned = sum(1 for selected_region, _ in selected if selected_region == region)
                manifest["region_progress"][region] = {"complete_pairs": complete, "planned_pairs": planned,
                                                        "status": "complete" if complete == planned else "in_progress"}
                save_manifest()
                print(f"Ready {region} [{complete}/{planned}]: {PurePosixPath(rgb.filename).name}", flush=True)
        def parallel_worker(jobs):
            try:
                with HTTPRangeReader() as worker_remote, zipfile.ZipFile(worker_remote) as worker_archive:
                    with progress_lock:
                        readers.append(worker_remote)
                    while not stop_workers.is_set():
                        try:
                            region_jobs = jobs.get_nowait()
                        except queue.Empty:
                            break
                        for region, (rgb, label) in region_jobs:
                            run_pair(worker_archive, region, rgb, label)
            except BaseException:
                stop_workers.set()
                raise
        try:
            if workers == 1:
                for region, (rgb, label) in selected:
                    run_pair(archive, region, rgb, label)
            else:
                jobs = queue.Queue()
                for region in sorted(set(regions)):
                    region_jobs = [item for item in selected if item[0] == region]
                    if any("label" not in entries.get(pair[0].filename, {}) for _, pair in region_jobs):
                        jobs.put(region_jobs)
                    else:
                        for _, (rgb, label) in region_jobs:
                            run_pair(archive, region, rgb, label)
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = [executor.submit(parallel_worker, jobs) for _ in range(min(workers, jobs.qsize()))]
                    for future in futures:
                        future.result()
            manifest["status"] = "complete"
        except Exception as exc:
            manifest["status"] = "failed"
            manifest["error"] = str(exc)
            raise
        finally:
            save_manifest()
        print(f"Saved {len(selected)} complete pairs; {required:,} extracted bytes; "
              f"{sum(reader.bytes_transferred for reader in readers):,} transferred bytes; "
              f"{time.monotonic() - started:.2f}s; manifest: {manifest_path}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--list", action="store_true", help="List regions and complete RGB/label pair counts")
    modes.add_argument("--plan", action="store_true", help="Report exact selected sizes from the ZIP directory; no image download")
    parser.add_argument("--regions", nargs="+", help="Region names (space or comma separated)")
    parser.add_argument("--limit", type=int, default=1, help="Maximum complete image pairs per region (default: 1)")
    parser.add_argument("--seed", type=int, default=None, help="Random sample seed per region; omit for lexicographic selection")
    parser.add_argument("--workers", type=int, choices=(1, 2), default=1, help="Independent HTTP readers (default: 1; maximum: 2)")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "pilot")
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be positive")
    regions = [part for value in (args.regions or []) for part in value.split(",") if part]
    if not args.list and not regions:
        parser.error("Specify --list or --regions REGION [REGION ...]")
    try:
        prepare(regions, args.limit, args.output, args.list, args.plan, args.seed, args.workers)
    except (RangeDownloadError, ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
