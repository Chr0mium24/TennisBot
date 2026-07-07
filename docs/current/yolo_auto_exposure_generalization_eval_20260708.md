# YOLO Auto-Exposure Generalization Evaluation - 2026-07-08

## Summary

This evaluation checks how the fixed-exposure ROI-trained detectors behave on
the older auto-exposure `cam1_first700` data.

The result is mixed:

- Direct full-frame inference on the old `1920x1080` auto-exposure frames works
  well on this small sample.
- Oracle-centered `1024x576` ROI inference on the same frames is weaker and has
  more false positives on negative frames.
- The model seed checkpoint was `artifacts/models/tennis_ball_yolo/model.pt`, so
  these runs are fine-tunes from an existing detector, not from a generic
  pretrained model. Good old-data behavior may partly come from retained prior
  detector behavior.

This result validates only detector behavior on local labeled images. It does
not validate ROS/Gazebo, stereo triangulation, trajectory prediction, or chassis
control.

## Definitions

Recall is:

`TP / (TP + FN)`

The threshold sweep fixes the model confidence threshold and then computes
detection-level precision/recall using IoU `0.5`.

In these notes:

- Low threshold means `conf=0.05`: accept weak detections to reduce misses.
- Medium threshold means `conf=0.25`: a more conservative runtime threshold.
- Lower thresholds usually improve recall but increase false positives.

## Evaluation Data

Source split:

`tools/yolo/workspace/dataset/splits/cam1_first700`

Generated evaluation package:

`tools/yolo/workspace/runs/auto_exposure_cam1_first700_generalization_eval_20260708.zip`

SHA256:

`ea1caf9b32a162b99ca84fd84c4a48365ece494b6b9e84ca9ad5429448f0a4ea`

Counts:

| item | count |
|---|---:|
| total images | `121` |
| positive images | `109` |
| empty images | `12` |
| train split images | `109` |
| val split images | `12` |

Two views were evaluated:

| view | description |
|---|---|
| `full` | original `1920x1080` auto-exposure image |
| `roi1024_oracle` | `1024x576` crop centered from the ground-truth ball for positives, center crop for negatives |

The oracle ROI view isolates exposure/domain behavior from tracking failure. It
is not a real runtime result because it uses labels to center the crop.

## Models Evaluated

| model id | checkpoint | inference image size |
|---|---|---:|
| `roi1024_i960_best` | `fixed_exposure_roi1024x576_3000_imgsz960_batch40_20260708/weights/best.pt` | `960` |
| `roi1024_i960_epoch20` | `fixed_exposure_roi1024x576_3000_imgsz960_batch40_20260708/weights/epoch20.pt` | `960` |
| `roi1024_i640_best` | `fixed_exposure_roi1024x576_3000_imgsz640_batch64_20260708/weights/best.pt` | `640` |

## Results

All rows use IoU `0.5`.

### Full-Frame Auto-Exposure

| model | conf | precision | recall | FP | FN | negative images with FP |
|---|---:|---:|---:|---:|---:|---:|
| `roi1024_i960_best` | `0.05` | `0.714` | `0.963` | `42` | `4` | `3` |
| `roi1024_i960_best` | `0.25` | `0.885` | `0.917` | `13` | `9` | `2` |
| `roi1024_i960_epoch20` | `0.05` | `0.805` | `0.982` | `26` | `2` | `2` |
| `roi1024_i960_epoch20` | `0.25` | `0.879` | `0.936` | `14` | `7` | `1` |
| `roi1024_i640_best` | `0.05` | `0.855` | `0.972` | `18` | `3` | `2` |
| `roi1024_i640_best` | `0.25` | `0.962` | `0.917` | `4` | `9` | `2` |

On the full-frame old auto-exposure images, generalization is good on this
sample. The best recall-oriented choice is `roi1024_i960_epoch20` at low
threshold (`recall=0.982`, `FN=2`). The cleaner medium-threshold choice is
`roi1024_i640_best` at `conf=0.25` (`precision=0.962`, `recall=0.917`, `FP=4`).

### Oracle 1024x576 ROI Auto-Exposure

| model | conf | precision | recall | FP | FN | negative images with FP |
|---|---:|---:|---:|---:|---:|---:|
| `roi1024_i960_best` | `0.05` | `0.595` | `0.862` | `64` | `15` | `8` |
| `roi1024_i960_best` | `0.25` | `0.746` | `0.835` | `31` | `18` | `8` |
| `roi1024_i960_epoch20` | `0.05` | `0.691` | `0.881` | `43` | `13` | `7` |
| `roi1024_i960_epoch20` | `0.25` | `0.782` | `0.853` | `26` | `16` | `6` |
| `roi1024_i640_best` | `0.05` | `0.763` | `0.826` | `28` | `19` | `5` |
| `roi1024_i640_best` | `0.25` | `0.854` | `0.807` | `15` | `21` | `4` |

The ROI view is worse than full-frame on this old auto-exposure set. That means
the fixed-exposure ROI detector does not automatically become robust to old
auto-exposure ROI crops. If the old runtime script switches to ROI mode, it
still needs sequence-level validation.

## Interpretation

The current detector has not obviously lost the old auto-exposure full-frame
behavior, especially for the `epoch20` and `imgsz640` checkpoints. However, this
is not enough to claim broad domain generalization:

- the old auto-exposure evaluation set is small (`121` images, `12` negatives);
- the seed checkpoint likely already knew similar old auto-exposure imagery;
- only cam1 indoor samples were checked;
- no sequence-level tracking/runtime behavior was evaluated.

Practical takeaway:

- For the old full-frame auto-exposure script, the model is likely usable on
  similar indoor cam1 data.
- For the new `1024x576` ROI runtime, old auto-exposure generalization is only
  moderate, not excellent.
- A real decision should use replay on the original auto-exposure sequences,
  with the same crop policy and confidence threshold as runtime.
