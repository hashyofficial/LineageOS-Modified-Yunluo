# LineageOS Modified — Redmi Pad (yunluo)

This repository prepares a **fastboot firmware conversion project** for a prebuilt LineageOS OTA ZIP (containing `payload.bin`).

## Stage 1: inspect the supplied OTA

GitHub Actions workflow: **Inspect LineageOS OTA**.

1. Download the publicly shared Google Drive folder using `gdown`.
2. Inventory files and inspect ZIP metadata without expanding multi-gigabyte images.
3. Inspect `payload.bin` using `payload-dumper-go -l`.
4. Publish an inspection report as a workflow artifact and job summary.

Source folder: https://drive.google.com/drive/folders/1SWjco5A8nD8ml8GjiaqNKxORHI3YXXmC?usp=sharing

**Important:** This initial workflow **does not flash or modify any device**. A fastboot flashing package needs an exact partition plan based on the inspected payload, dynamic partition metadata, A/B slots, and device firmware requirements. A recovery OTA is not necessarily a complete factory firmware. No resulting images should be treated as bootable or flashed without validating the partition mapping and matching base firmware.

## Run

Open **Actions → Inspect LineageOS OTA → Run workflow** (or use the automatic first run when the workflow is committed). Read the job summary and download the `lineageos-ota-inspection` artifact.

If the download is denied, set the Google Drive folder and its files to **Anyone with the link — Viewer**. The workflow uses no private Google account or credentials.


## Stage 2: Play-only Android 16 ROM (experimental)

Workflow: **Build Play-Only LineageOS OTA (Experimental)**.

Successful offline build: https://github.com/hashyofficial/LineageOS-Modified-Yunluo/actions/runs/40209531537

- Original input: `lineage-23.0-20251015-UNOFFICIAL-yunluo.zip` (Android 16, A/B).
- Upstream input for extraction only: MindTheGapps Android 16 ARM64, pinned 20261023 release.
- `product.img`: `GmsCore.apk`, `Phonesky.apk`, necessary permissions, sysconfig, overlays and GMS fs-verity certificate.
- `system_ext.img`: `GoogleServicesFramework.apk` and matching privileged-app permissions.
- Nothing else from the upstream GApps package is added: no Gmail, YouTube, Chrome, Google app/Assistant, Photos, Google Setup Wizard, or sync-adapter APKs.
- Original partition images are rebuilt from ext4 with file metadata preserved. Only the explicitly allowlisted files are added.
- OTA payload, ZIP, and AVB images are rebuilt/re-signed and `avbroot ota verify` has passed. This verifies cryptographic and structural consistency **only**. Actual recovery acceptance, device compatibility, and successful boot have **not** been tested.
- **Important:** The source ROM has verified boot disabled (vbmeta flags 0x3). `avbroot` requires `--clear-vbmeta-flags` to repack the OTA, which changes that behavior. The result is **not** a drop-in replacement for the original ROM, and no assumption should be made about the device's trust configuration.
- The workflow generates ephemeral private AVB/OTA signing keys. They are not uploaded, released, or committed. Future updates with those same signing identities are not possible unless separately handled; do not relock the bootloader or flash without a compatible device-specific installation plan.
- The output artifact is marked **EXPERIMENTAL**. Do **not** install until custom recovery signature trust, AVB chain, and dynamic partition group sizing have been independently confirmed for yunluo.

The build scripts are in the repository; the ROM images and GApps binaries are downloaded into temporary GitHub Actions runners rather than committed to source control. Do not redistribute Google's proprietary apps without appropriate rights.
