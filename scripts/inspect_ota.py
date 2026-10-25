#!/usr/bin/env python3
"""Non-destructive inspection of a public Android OTA and its payload.bin."""
import json
import os
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

SOURCE = Path(os.environ.get("OTA_DOWNLOAD_DIR", "downloads"))
OUT = Path(os.environ.get("OTA_REPORT_DIR", "inspection"))
OUT.mkdir(parents=True, exist_ok=True)
MAX_ITEMS = 250
MAX_TEXT = 20000
files = sorted((p for p in SOURCE.rglob("*") if p.is_file()), key=lambda p: str(p))
data = {"source": str(SOURCE), "files": [], "candidates": [], "warnings": []}
lines = ["# LineageOS OTA inspection — Redmi Pad (yunluo)", "",
         "This is an **inspection only**. No image has been flashed or declared bootable.", ""]

def size(n):
    for suffix in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or suffix == "TiB":
            return f"{n:.1f} {suffix}"
        n /= 1024

def add(*items):
    lines.extend(items)

def get_payload_header(handle):
    header = handle.read(24)
    if len(header) < 20 or header[:4] != b"CrAU":
        return {"valid_magic": False, "header_prefix_hex": header[:16].hex()}
    version, manifest_size = struct.unpack(">QQ", header[4:20])
    signature_size = struct.unpack(">I", header[20:24])[0] if version >= 2 and len(header) >= 24 else 0
    return {"valid_magic": True, "version": version,
            "manifest_size": manifest_size, "metadata_signature_size": signature_size}

def list_partitions(path):
    try:
        p = subprocess.run(["payload-dumper-go", "-l", str(path)],
                           capture_output=True, text=True, timeout=240)
        return {"exit_code": p.returncode,
                "output": (p.stdout + "\n" + p.stderr).strip()[:MAX_TEXT]}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"exit_code": -1, "output": str(e)}

add("## Downloaded files", "")
if not files:
    data["warnings"].append("No files downloaded. Verify Google Drive sharing permissions and workflow download log.")
    add("**No files found.** Check the gdown step and Google Drive sharing.", "")
for file in files[:MAX_ITEMS]:
    rel = file.relative_to(SOURCE).as_posix()
    record = {"path": rel, "size_bytes": file.stat().st_size}
    data["files"].append(record)
    add(f"- {rel} — {size(record['size_bytes'])}")
if len(files) > MAX_ITEMS:
    add(f"- ...and {len(files)-MAX_ITEMS} more files (see download logs).")
add("", "## OTA candidates and partition manifests", "")

for file in files:
    record = {"file": str(file.relative_to(SOURCE))}
    if file.suffix.lower() == ".zip" and zipfile.is_zipfile(file):
        with zipfile.ZipFile(file) as z:
            members = z.infolist()
            payloads = [m for m in members if m.filename == "payload.bin" or m.filename.endswith("/payload.bin")]
            if not payloads:
                continue
            record["format"] = "zip"
            record["payload_entries"] = [m.filename for m in payloads]
            record["zip_entries"] = [{"name": m.filename, "uncompressed_size": m.file_size}
                                     for m in members[:MAX_ITEMS]]
            add(f"### {record['file']}", "",
                f"ZIP entries: **{len(members)}**; payload entries: **{len(payloads)}**.", "")
            for entry in payloads:
                with z.open(entry) as stream:
                    header = get_payload_header(stream)
                record.setdefault("payload_headers", []).append({"entry": entry.filename, **header})
                add(f"- Payload: {entry.filename} ({size(entry.file_size)}) — "
                    f"CrAU magic: {header.get('valid_magic')}, "
                    f"version: {header.get('version', 'unknown')}")
            record["metadata"] = {}
            for m in members:
                name = m.filename
                if name in ("META-INF/com/android/metadata", "payload_properties.txt",
                            "dynamic_partitions_op_list") or name.endswith("/dynamic_partitions_op_list"):
                    if m.file_size <= 1024 * 1024:
                        with z.open(m) as stream:
                            snippet = stream.read(MAX_TEXT).decode("utf-8", "replace")
                        record["metadata"][name] = snippet
                        add("", f"**{name}**", "", "~~~text", snippet.rstrip(), "~~~")
            add("", "**Archive contents (first 100):**", "")
            for item in members[:100]:
                add(f"- {item.filename} — {size(item.file_size)}")
            add("")
    elif file.name.lower() == "payload.bin":
        record["format"] = "raw_payload"
        with file.open("rb") as stream:
            header = get_payload_header(stream)
        record["payload_headers"] = [header]
        add(f"### {record['file']}", "",
            f"Raw payload — CrAU magic: {header.get('valid_magic')}; version: {header.get('version', 'unknown')}", "")
    else:
        continue

    report = list_partitions(file)
    record["dumper"] = report
    add("**Partition listing from payload-dumper-go:**", "",
        "~~~text", report["output"] or "(no output)", "~~~", "")
    if report["exit_code"] != 0:
        data["warnings"].append(f"payload-dumper-go could not list partitions for {record['file']}")
    for body in record.get("metadata", {}).values():
        for entry in body.splitlines():
            if entry.startswith("post-device=") and "yunluo" not in entry.lower():
                data["warnings"].append(f"OTA post-device does not say yunluo: {entry}")
    data["candidates"].append(record)

if not data["candidates"]:
    data["warnings"].append("No OTA ZIP with payload.bin, or raw payload.bin, was found.")
if len(data["candidates"]) > 1:
    data["warnings"].append("Multiple payloads found. Select and validate the intended ROM before conversion.")
if data["warnings"]:
    add("## Warnings", "")
    for warning in data["warnings"]:
        add(f"- {warning}")
    add("")

add("## Next checks before building fastboot firmware", "",
    "- Match OTA post-device and build fingerprint to the intended yunluo hardware.",
    "- Determine whether the payload is a full OTA or requires base images (incremental/delta).",
    "- Identify physical partitions, logical/dynamic partitions, slot suffixes, and required firmware components.",
    "- Verify stock firmware compatibility. An OTA alone might lack factory bootloader/firmware partitions.",
    "- Do not flash anything until the image set and device-specific flashing plan are validated.", "")

(OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
(OUT / "report.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary, "a", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
print(f"Inspected {len(files)} downloaded files; {len(data['candidates'])} payload candidate(s).")
for warning in data["warnings"]:
    print("WARNING:", warning)
if not data["candidates"] or all(c["dumper"]["exit_code"] != 0 for c in data["candidates"]):
    sys.exit(2)
