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
