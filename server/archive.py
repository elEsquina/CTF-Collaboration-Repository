import re
import stat
import zipfile
import zlib
from pathlib import Path
from fastapi import HTTPException

DOCKER_FILES = {'Dockerfile', 'compose.yaml', 'compose.yml', 'docker-compose.yml', 'docker-compose.yaml'}

def reject(message):
    raise HTTPException(422, message)

def validate_extract(archive: Path, destination: Path | None, requires_docker: bool, settings):
    """Inspect every entry, then stream bounded extraction without trusting extractall."""
    try:
        with zipfile.ZipFile(archive) as zipped:
            entries = zipped.infolist()
            if len(entries) > settings.max_zip_members:
                reject('ZIP contains too many entries.')
            paths = []
            seen = set()
            total = 0
            for entry in entries:
                name = entry.orig_filename
                parts = name.rstrip('/').split('/')
                if (not name or '\\' in name or '\x00' in name or name.startswith('/')
                    or any(p in ('', '.', '..') or ':' in p or any(ord(c) < 32 for c in p) for p in parts)
                    or len(name.encode('utf-8')) > 2048 or len(parts) > 32
                    or any(len(part.encode('utf-8')) > 255 for part in parts)):
                    reject('ZIP contains an unsafe path.')
                mode = entry.external_attr >> 16
                kind = stat.S_IFMT(mode)
                if kind not in (0, stat.S_IFREG, stat.S_IFDIR) or (kind == stat.S_IFDIR and not entry.is_dir()):
                    reject('ZIP contains a symlink or unsupported special file.')
                if entry.flag_bits & 1:
                    reject('Encrypted ZIP archives are not supported.')
                if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    reject('Use ZIP storage or Deflate compression.')
                canonical = '/'.join(parts).casefold()
                if canonical in seen:
                    reject('ZIP contains duplicate or conflicting paths.')
                seen.add(canonical)
                total += entry.file_size
                if (entry.file_size > settings.max_file_bytes or total > settings.max_extracted_bytes
                    or entry.file_size > max(entry.compress_size, 1) * settings.max_compression_ratio):
                    reject('ZIP exceeds the extraction size or compression ratio limit.')
                paths.append((entry, parts))
            files = {tuple(parts) for entry, parts in paths if not entry.is_dir()}
            folded_files = {tuple(p.casefold() for p in path) for path in files}
            for _, parts in paths:
                if any(tuple(p.casefold() for p in parts[:i]) in folded_files for i in range(1, len(parts))):
                    reject('ZIP contains conflicting file and directory paths.')
            # Strip one shared enclosing directory only for layout validation.
            root = {parts[0] for _, parts in paths}
            offset = 1 if len(root) == 1 and all(len(parts) > 1 or entry.is_dir() for entry, parts in paths) else 0
            relative_files = {tuple(parts[offset:]) for entry, parts in paths if not entry.is_dir()}
            relative_dirs = {tuple(parts[offset:]) for entry, parts in paths if entry.is_dir()}
            if requires_docker:
                if not any((name,) in relative_files for name in DOCKER_FILES):
                    reject('Docker challenges need a Dockerfile or Compose file at the archive root (or inside one enclosing folder).')
                if ('dist',) not in relative_dirs and not any(p and p[0] == 'dist' and len(p) > 1 for p in relative_files):
                    reject('Docker challenges need a dist/ directory.')
            actual_total = 0
            for entry, parts in paths:
                target = destination.joinpath(*parts) if destination else None
                if entry.is_dir():
                    if target:
                        target.mkdir(parents=True, exist_ok=True)
                    continue
                if target:
                    target.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with zipped.open(entry) as source:
                    output = target.open('xb') if target else None
                    try:
                        while chunk := source.read(64 * 1024):
                            written += len(chunk)
                            actual_total += len(chunk)
                            if written > settings.max_file_bytes or actual_total > settings.max_extracted_bytes:
                                reject('ZIP exceeds extraction limits.')
                            if output:
                                output.write(chunk)
                    finally:
                        if output:
                            output.close()
                if written != entry.file_size:
                    reject('ZIP contains an invalid file size.')
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, NotImplementedError, EOFError, ValueError, zlib.error) as exc:
        raise HTTPException(422, 'The ZIP is corrupted, encrypted, or uses unsupported compression.') from exc

def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:70] or 'challenge'
