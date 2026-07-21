# Search-S3d Held-Out Miss Audit - 2026-07-05

## Scope

This audits the current best teacher, S3d `best_recall.pt`, on the held-out
`20260701_155008` sequence. It is an offline vision audit only and does not
validate real ROS/chassis, stereo triangulation, prediction, or chassis control.

## Inputs

- Checkpoint:
  `tools/yolo/workspace/runs/temporal_heatmap/search_s3d_temporal_heatmap_w5_960x540_pseudo989_synth500_20260705/best_recall.pt`
- Labels root:
  `tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`
- Validation token: `20260701_155008`
- Threshold: `0.40`
- Match radius: `12` px at `960x540`

## Files

- Audit directory:
  `tools/yolo/workspace/runs/miss_audit/s3d_best_recall_155008_20260705`
- Predictions CSV:
  `tools/yolo/workspace/runs/miss_audit/s3d_best_recall_155008_20260705/predictions.csv`
- Misses CSV:
  `tools/yolo/workspace/runs/miss_audit/s3d_best_recall_155008_20260705/misses.csv`
- False positives CSV:
  `tools/yolo/workspace/runs/miss_audit/s3d_best_recall_155008_20260705/false_positives.csv`
- Contact sheet:
  `tools/yolo/workspace/runs/miss_audit/s3d_best_recall_155008_20260705/miss_contact_sheet.jpg`

## Reproduced Metrics

| item | count |
|---|---:|
| samples | 253 |
| positives | 93 |
| negatives | 160 |
| TP | 72 |
| FN low score | 1 |
| FN bad localization | 20 |
| FP on negative frames | 128 |

Recall is `72 / 93 = 0.774`, matching the saved S3d result.

## Miss Pattern

The misses are concentrated in two held-out spans:

- `cam1` frames `72-83`
- `cam2` frames `83-95`

There is one additional miss at `cam2` frame `126`.

Most misses are not low-confidence misses. The model often produces a strong
peak, but the peak is on the ceiling/left-side background instead of the ball.

| miss type | count |
|---|---:|
| low score | 1 |
| bad localization | 20 |

Miss distance statistics:

| statistic | distance px |
|---|---:|
| min | 57.20 |
| median | 310.48 |
| p90 | 332.71 |
| max | 338.27 |

Miss score statistics:

| statistic | score |
|---|---:|
| min | 0.387 |
| median | 0.783 |
| max | 0.957 |

## Top-K Candidate Check

I tested NMS-style top-k heatmap candidates on S3d. Top-k did not improve
recall, which means the true ball is generally not present as a secondary peak
in the current heatmap.

| threshold | k | recall | precision |
|---:|---:|---:|---:|
| 0.20 | 1 | 0.774 | 0.293 |
| 0.20 | 5 | 0.774 | 0.169 |
| 0.30 | 1 | 0.774 | 0.308 |
| 0.30 | 5 | 0.774 | 0.214 |
| 0.40 | 1 | 0.774 | 0.327 |
| 0.40 | 5 | 0.774 | 0.257 |
| 0.60 | 1 | 0.763 | 0.410 |
| 0.60 | 5 | 0.763 | 0.376 |

## Decision

Algorithm-only top-k selection will not raise S3d above `0.90` recall. The
remaining held-out failures need real training signal for the specific
background/trajectory pattern:

- add or review real labels around the held-out-like `cam1`/`cam2` span where
  the ball crosses the net/center region;
- add hard negatives from the ceiling/left-side background peaks;
- create targeted synthetic samples that place the ball near the green GT
  region while preserving the ceiling/left-side distractors.

The next training attempt should be based on these targeted real/hard-negative
samples, not more unreviewed self-labeling.
