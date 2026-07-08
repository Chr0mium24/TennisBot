# YOLO Tiny P2 No-P5 Final Trainpool Result - 2026-07-09

## Scope

This records the P2-head YOLO training run requested to check whether a
stride-4 detection head helps the current fixed-exposure tiny-ball failure.

This is a detector-only experiment. It does not validate stereo triangulation,
trajectory prediction, ROS/Gazebo, or chassis control.

## Setup

Remote host:

`anilam@10.31.151.120`

Training run:

`runs/detect/tools/yolo/workspace/runs/training/final_trainpool_tiny_p2_no_p5_imgsz960_batch32_20260708`

The run path is under `runs/detect/...` because Ultralytics resolved the
relative `project=tools/yolo/workspace/runs/training` argument under its default
`runs/detect` root. This matches earlier local experiment behavior.

| item | value |
|---|---|
| config | `tools/yolo/configs/tennis_yolo26_tiny_p2_no_p5.yaml` |
| heads | `P2/P3/P4` |
| strides | `4,8,16` |
| seed weights | `artifacts/models/tennis_ball_yolo/model.pt` |
| transferred weights | `70/774` |
| dataset | `tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_20260708/data.yaml` |
| images | `13,939` total, `12,549` train, `1,390` val |
| image size | `960` |
| batch | `32` |
| workers | `8` |
| GPU | `NVIDIA GeForce RTX 5070 Ti` |
| observed GPU memory | about `11.9G` during training |
| training time | `1.019 h` |

The remote training venv has Ultralytics and Torch but not the full tools/yolo
runtime dependency set. Final benchmark evaluation was therefore run by calling
`tennisbot_yolo.benchmark.cmd_benchmark_eval_final_raw` directly instead of the
top-level CLI, which imports the annotator and requires `uvicorn`.

## Training Result

Training early-stopped at epoch `30` because `mAP50-95` did not improve for
`8` epochs. Best checkpoint was epoch `22`.

| selection | epoch | precision | recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|
| best recall | `19` | `0.79592` | `0.58534` | `0.64427` | `0.38306` |
| best mAP50 | `18` | `0.80495` | `0.58179` | `0.64717` | `0.38484` |
| best mAP50-95 / `best.pt` | `22` | `0.82620` | `0.56577` | `0.64495` | `0.38971` |
| final / `last.pt` | `30` | `0.80643` | `0.55987` | `0.61928` | `0.37037` |

Internal validation is lower than the current promoted tiny-copy-paste model's
best internal row (`recall=0.64250`, `mAP50-95=0.40745`). The deciding metric is
the frozen raw benchmark below.

Checkpoint hashes:

| checkpoint | size | SHA256 |
|---|---:|---|
| `best.pt` | `1,913,019 bytes` | `71c17453e52c56d19c449fcfb17913fa9683f7784b68f75cb680b2cd1ad233cb` |
| `last.pt` | `1,913,019 bytes` | `2908c69d6206cbbfe6292da3a3014945cc4a003fffda6c5698e800738d3ce5bd` |
| `epoch20.pt` | `6,160,989 bytes` | `a79e8f3dd947bd5dc33ad170a8cafe0697b437ef1a460baa597e35d8db38a45b` |

## Final Raw Benchmark - Best Checkpoint

Model:

`runs/detect/tools/yolo/workspace/runs/training/final_trainpool_tiny_p2_no_p5_imgsz960_batch32_20260708/weights/best.pt`

Benchmark:

`tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708/manifest_remote_eval.jsonl`

| imgsz | conf | overall R/P | fixed R/P | small R/P | medium R/P | large R/P | empty FP imgs | est stereo FPS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `960` | `0.05` | `0.516 / 0.564` | `0.386 / 0.717` | `0.009 / 0.143` | `0.371 / 0.812` | `0.951 / 0.603` | `15` | `130.15` |
| `960` | `0.25` | `0.453 / 0.916` | `0.327 / 0.961` | `0.000 / n/a` | `0.286 / 1.000` | `0.852 / 0.924` | `2` | `130.15` |
| `1280` | `0.05` | `0.585 / 0.335` | `0.471 / 0.325` | `0.134 / 0.333` | `0.543 / 0.302` | `0.951 / 0.382` | `27` | `96.47` |
| `1280` | `0.25` | `0.526 / 0.618` | `0.408 / 0.711` | `0.062 / 0.333` | `0.429 / 0.833` | `0.915 / 0.650` | `7` | `96.47` |
| `1536` | `0.05` | `0.682 / 0.417` | `0.601 / 0.462` | `0.232 / 0.400` | `0.943 / 0.868` | `0.972 / 0.481` | `38` | `77.24` |
| `1536` | `0.25` | `0.619 / 0.696` | `0.538 / 0.741` | `0.143 / 0.615` | `0.914 / 0.941` | `0.923 / 0.744` | `15` | `77.24` |

Best checkpoint readout:

- `imgsz=1536` is the only setting where the P2 head materially helps tiny
  fixed-exposure balls.
- At `conf=0.05`, small recall improves to `0.232`, but empty false-positive
  images rise to `38`.
- At `conf=0.25`, small recall is lower (`0.143`), but precision is much
  cleaner and empty false-positive images drop to `15`.
- Estimated stereo FPS stays above the `50 FPS` target in all tested rows.

## Checkpoint Comparison at ImgSz1536

| checkpoint | conf | overall R/P | fixed R/P | small R/P | medium R/P | large R/P | empty FP imgs | est stereo FPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `best.pt` | `0.05` | `0.682 / 0.417` | `0.601 / 0.462` | `0.232 / 0.400` | `0.943 / 0.868` | `0.972 / 0.481` | `38` | `77.24` |
| `best.pt` | `0.25` | `0.619 / 0.696` | `0.538 / 0.741` | `0.143 / 0.615` | `0.914 / 0.941` | `0.923 / 0.744` | `15` | `77.24` |
| `epoch20.pt` | `0.05` | `0.630 / 0.475` | `0.552 / 0.569` | `0.232 / 0.394` | `0.771 / 0.844` | `0.908 / 0.520` | `30` | `77.10` |
| `epoch20.pt` | `0.25` | `0.519 / 0.754` | `0.439 / 0.860` | `0.107 / 0.706` | `0.629 / 0.917` | `0.817 / 0.753` | `4` | `77.10` |
| `last.pt` | `0.05` | `0.651 / 0.436` | `0.587 / 0.508` | `0.232 / 0.413` | `0.914 / 0.941` | `0.915 / 0.473` | `35` | `77.40` |
| `last.pt` | `0.25` | `0.595 / 0.669` | `0.543 / 0.747` | `0.179 / 0.690` | `0.857 / 1.000` | `0.859 / 0.689` | `18` | `77.40` |

`last.pt` is interesting if the only goal is medium-threshold small recall:
`small recall=0.179` at `conf=0.25`, better than `best.pt` at the same
threshold. It is worse on large recall and overall recall than `best.pt`.

## Comparison With Current Promoted Model

Current promoted model from
`docs/current/yolo_tiny_fixed_copy_paste_training_result_20260708.md`:

| model | imgsz | conf | overall R/P | fixed R/P | small R/P | medium R/P | large R/P | empty FP imgs | est stereo FPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| promoted tiny-copy-paste | `1536` | `0.05` | `0.616 / 0.459` | `0.511 / 0.483` | `0.080 / 0.200` | `0.829 / 0.558` | `0.986 / 0.560` | `33` | `80.09` |
| P2 no-P5 `best.pt` | `1536` | `0.05` | `0.682 / 0.417` | `0.601 / 0.462` | `0.232 / 0.400` | `0.943 / 0.868` | `0.972 / 0.481` | `38` | `77.24` |
| promoted tiny-copy-paste | `1536` | `0.25` | `0.592 / 0.500` | `0.502 / 0.533` | `0.071 / 0.200` | `0.800 / 0.596` | `0.951 / 0.611` | `29` | `80.09` |
| P2 no-P5 `best.pt` | `1536` | `0.25` | `0.619 / 0.696` | `0.538 / 0.741` | `0.143 / 0.615` | `0.914 / 0.941` | `0.923 / 0.744` | `15` | `77.24` |

## Readout

The P2 head is useful, but this exact model is not a final solution.

- It improves the important fixed/tiny failure mode on the frozen raw benchmark.
- At `imgsz=1536, conf=0.05`, small recall rises from `0.080` to `0.232`.
- At `imgsz=1536, conf=0.25`, small recall rises from `0.071` to `0.143` while
  precision and empty-frame false positives are better than the current promoted
  model.
- The model still misses most small balls: `86 / 112` small benchmark objects
  are missed even at `imgsz=1536, conf=0.05`.
- The P2 model loses a little large-target recall relative to the promoted
  model, especially at `conf=0.25`.
- It remains above the estimated stereo FPS target, so speed is not the blocker.

Decision:

- Do not promote this model as-is.
- Keep P2/no-P5 as a promising direction.
- The next detector-side experiment should combine P2 with stronger capacity or
  better real tiny fixed-exposure samples, rather than repeating this exact
  tiny-width run for more epochs.
- Runtime-side temporal evidence is still needed for 4-8px balls; this
  detector-only run does not prove the real catch loop.
