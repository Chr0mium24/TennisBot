# YOLO Dataset Backup Label Merge - 2026-07-03

## Scope

Merged the newly copied backup labels from:

- `tools/yolo/workspace/dataset/dataset_backup/labels`

into the current YOLO dataset labels at:

- `tools/yolo/workspace/dataset/labels/0260701`

The backup folder contained labels only. Labels were copied only when a matching image basename existed under:

- `tools/yolo/workspace/dataset/images/0260701`

The dataset and generated sprite artifacts remain under ignored workspace paths and are not committed to Git.

## Merge Result

- Source backup labels: 515
- Labels copied into `labels/0260701`: 507
- Existing labels overwritten: 4
- Labels skipped because no matching image exists: 8
- Final `labels/0260701` label count: 507
- Final workspace label count: 1168
- Final workspace image count: 17900

Skipped labels:

- `20260701_152729_cam1_frame_000001.txt`
- `20260701_152729_cam1_frame_000002.txt`
- `20260701_152729_cam1_frame_000003.txt`
- `20260701_152729_cam1_frame_000004.txt`
- `20260701_152729_cam1_frame_000005.txt`
- `20260701_152729_cam1_frame_000006.txt`
- `20260701_152729_cam1_frame_000007.txt`
- `20260701_152729_cam1_frame_000008.txt`

## Sprite Regeneration

Removed the previous generated sprite output:

```bash
rm -rf -- tools/yolo/workspace/runs/sprites
```

Regenerated sprite candidates:

```bash
bun scripts/yolo.ts sprites extract --overwrite
```

Generation output:

- Sprite candidates: 254
- Skipped images: 17646
- Manifest: `tools/yolo/workspace/runs/sprites/manifest.jsonl`

Review API count after regeneration:

- Total sprites: 254
- `candidate`: 254
- From `0260701` labels: 145
- From `cam1` labels: 109

## Review Server

Started the sprite review server on:

```bash
bun scripts/yolo.ts sprites review --host 0.0.0.0 --port 8766
```

Verified local health check:

```bash
curl -fsS http://127.0.0.1:8766/api/health
```

LAN review URL:

- `http://10.31.55.254:8766/`

Local review URL:

- `http://127.0.0.1:8766/`
