#!/usr/bin/env python3
"""Inject exactly three Play APKs and support files into afsr ext4 metadata/tree.

No original files are removed/overwritten. This tool produces an intermediate
filesystem tree, not flashable firmware by itself.
"""
import argparse
import copy
import hashlib
import json
import shutil
import tomllib
import zipfile
from pathlib import Path
import tomli_w

PRODUCT = (
    "priv-app/GmsCore/GmsCore.apk",
    "priv-app/Phonesky/Phonesky.apk",
    "etc/permissions/privapp-permissions-google-product.xml",
    "etc/permissions/privapp-permissions-mtg.xml",
    "etc/default-permissions/default-permissions-google.xml",
    "etc/sysconfig/google.xml",
    "etc/sysconfig/google-hiddenapi-package-allowlist.xml",
    "etc/sysconfig/sysconfig-mtg.xml",
    "etc/security/fsverity/gms_fsverity_cert.der",
    "overlay/GmsOverlay.apk",
    "overlay/GmsSettingsOverlay.apk",
    "overlay/GmsSettingsProviderOverlay.apk",
)
SYSTEM_EXT = (
    "priv-app/GoogleServicesFramework/GoogleServicesFramework.apk",
    "etc/permissions/privapp-permissions-google-system-ext.xml",
)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gapps", type=Path, required=True)
    p.add_argument("--partition", choices=("product", "system_ext"), required=True)
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    prefix = "system/" + args.partition + "/"
    selected = PRODUCT if args.partition == "product" else SYSTEM_EXT
    original = args.metadata.read_text(encoding="utf-8")
    parsed = tomllib.loads(original)
    entries = parsed["entries"]
    by_path = {v["path"]: v for v in entries}
    for required in ("/", "/etc", "/priv-app"):
        if required not in by_path:
            raise RuntimeError(f"{args.partition}: image lacks {required}; refusing modification")
    made = []
    report = []

    def donor(target, kind):
        if kind == "Directory":
            d = by_path.get(str(Path(target).parent))
            if d and d["file_type"] == "Directory":
                return d
            return by_path["/priv-app"] if target.startswith("/priv-app") else by_path["/etc"]
        suffix = Path(target).suffix
        directory = str(Path(target).parent)
        choices = [e for e in entries if e["file_type"] == "RegularFile" and
                   str(Path(e["path"]).parent) == directory and
                   Path(e["path"]).suffix == suffix]
        if not choices:
            choices = [e for e in entries if e["file_type"] == "RegularFile" and
                       Path(e["path"]).suffix == suffix]
        if not choices:
            choices = [e for e in entries if e["file_type"] == "RegularFile"]
        if not choices:
            raise RuntimeError(f"No regular-file metadata donor in {args.partition}")
        return choices[0]

    def new_entry(path, kind):
        d = donor(path, kind)
        e = {"path": path, "file_type": kind,
             "file_mode": "755" if kind == "Directory" else "644",
             "uid": 0, "gid": 0}
        for k in ("mtime", "atime", "ctime", "crtime"):
            if k in d:
                e[k] = d[k]
        if "xattrs" in d:
            e["xattrs"] = copy.deepcopy(d["xattrs"])
        made.append(e)
        by_path[path] = e

    def ensure_dirs(path):
        parents = []
        cursor = Path(path).parent
        while str(cursor) not in by_path:
            if str(cursor) == "/":
                raise RuntimeError("Original image is missing root directory")
            parents.append(str(cursor))
            cursor = cursor.parent
        for directory in reversed(parents):
            new_entry(directory, "Directory")
            (args.tree / directory.lstrip("/")).mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(args.gapps) as z:
        names = set(z.namelist())
        for relative in selected:
            src = prefix + relative
            if src not in names:
                raise RuntimeError(f"Missing expected upstream GApps file: {src}")
            target = "/" + relative
            if target in by_path:
                raise RuntimeError(f"Would overwrite existing ROM file: {target}")
            ensure_dirs(target)
            file_out = args.tree / relative
            file_out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(src) as inp, file_out.open("wb") as out:
                shutil.copyfileobj(inp, out, length=1024 * 1024)
            new_entry(target, "RegularFile")
            with file_out.open("rb") as input_file:
                sha = hashlib.file_digest(input_file, "sha256").hexdigest()
            report.append({"partition": args.partition, "path": target,
                           "bytes": file_out.stat().st_size, "sha256": sha})

    args.metadata.write_text(original + "\n" + tomli_w.dumps({"entries": made}), encoding="utf-8")
    changed = tomllib.loads(args.metadata.read_text(encoding="utf-8"))
    new_paths = [x["path"] for x in changed["entries"]]
    assert len(set(new_paths)) == len(new_paths), "Duplicate path in fs metadata"
    assert all("/" + p in new_paths for p in selected)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Added {len(selected)} allowlisted files to {args.partition}; none overwritten/removed.")


if __name__ == "__main__":
    main()
