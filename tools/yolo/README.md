# TennisBot YOLO 工具

`tools/yolo` 是当前主线网球检测工具入口，包含：

- 标注前端/后端
- 已标注 bbox 的球 sprite 提取与审核
- 审核后球 sprite 的 copy-paste 数据增强
- 运行时模型包创建与验证
- 纯 YOLO OpenCV 检测 GUI

它不负责标定、双目几何、轨迹预测或运行时状态。

## 安装和测试

```bash
cd tools/yolo
uv sync
uv run pytest -q
```

默认 `uv sync` 只安装标注服务和模型包工具依赖，不安装 `torch`、
`ultralytics`、OpenCV、CUDA 或 NVIDIA Python 包。`uv.lock` 会记录
optional extras 的完整解析结果，所以能看到这些包名；只有运行
`uv sync --extra augment`、`uv sync --extra detect`、`uv sync --all-extras`
或 `uv run --extra ...` 时才会把它们装进当前环境。

如果旧的 `.venv` 曾经装过检测 extra，回到无 Torch/CUDA 环境时运行：

```bash
uv sync
```

不要加 `--inexact`、`--all-extras` 或 `--extra detect`。

## 标注前端

从仓库根目录启动：

```bash
bun scripts/yolo.ts annotate
```

或从工具目录直接启动：

```bash
uv run tennisbot-yolo annotate
```

默认值：

- `--images-root tools/yolo/yolo/dataset/images`
- `--labels-root tools/yolo/yolo/dataset/labels`
- `--excluded-file tools/yolo/yolo/dataset/excluded_images.txt`
- `--host 127.0.0.1`
- `--port 8765`

打开地址：

```text
http://127.0.0.1:8765
```

## 球 Sprite 提取和审核

这个流程保留原始 YOLO bbox 标签不变，只从已标注 bbox 生成透明球
sprite 候选。审核页面里调整的是 ellipse/alpha mask，不会改原标签。

从仓库根目录提取候选：

```bash
bun scripts/yolo.ts sprites extract
```

或从工具目录直接运行：

```bash
uv run --extra augment tennisbot-yolo sprites extract
```

默认值：

- `--images-root tools/yolo/yolo/dataset/images`
- `--labels-root tools/yolo/yolo/dataset/labels`
- `--excluded-file tools/yolo/yolo/dataset/excluded_images.txt`
- `--output-root tools/yolo/yolo/runs/sprites`

打开审核页面：

```bash
bun scripts/yolo.ts sprites review
```

默认地址：

```text
http://127.0.0.1:8766
```

审核通过的 sprite 会复制到 `tools/yolo/yolo/runs/sprites/approved/`，
拒绝的 sprite 会复制到 `tools/yolo/yolo/runs/sprites/rejected/`。

## Copy-Paste 数据增强

增强使用共享配置文件，不用单独按 copy-paste 命名：

```bash
bun scripts/yolo.ts augment copy-paste --config tools/yolo/configs/augmentation.toml
```

或从工具目录直接运行：

```bash
uv run --extra augment tennisbot-yolo augment copy-paste
```

默认输出：

- `tools/yolo/yolo/runs/copy_paste_aug/images`
- `tools/yolo/yolo/runs/copy_paste_aug/labels`
- `tools/yolo/yolo/runs/copy_paste_aug/manifest.jsonl`
- `tools/yolo/yolo/runs/copy_paste_aug/report.md`

这个命令不会旋转、倾斜或透视变换原始背景图；已有 bbox 标签会原样复制。
只有贴上的球会按 alpha mask 重新计算水平 YOLO bbox。验证集不生成合成样本。

## 验证模型包

```bash
uv run tennisbot-yolo package verify
```

默认值：

- `--path ../../artifacts/models/tennis_ball_yolo`

这个默认模型包已纳入 Git 跟踪，拉取仓库后应直接存在。其它 `artifacts/`
内容仍然保持忽略。

## 创建 dry-run 模型包

```bash
uv run tennisbot-yolo package create --dry-run
```

默认值：

- `--output-dir ../../artifacts/models/tennis_ball_yolo`
- `--default-model onnx`

dry-run 包只用于 loader 和流程验证，不代表真实推理能力。

## 创建真实模型包

创建真实包时必须显式传入至少一个模型文件：

```bash
uv run tennisbot-yolo package create \
  --model-pt ../../artifacts/model_candidates/tennis_ball_yolo/best.pt \
  --default-model pt
```

可选输入：

- `--model-pt`
- `--model-onnx`
- `--model-rknn`
- `--eval-report`
- `--eval-metrics`

如果同时提供多个模型，`--default-model` 必须指向其中一个。

## 纯 YOLO 检测 GUI

这个命令是唯一需要 `tools/yolo` 的 `detect` extra 的入口；它会通过
`ultralytics` 传递安装 Torch/CUDA 相关包。

```bash
uv run --extra detect tennisbot-yolo detect-gui
```

默认值：

- `--devices /dev/video0,/dev/video2`
- `--width 3840`
- `--height 2160`
- `--fps 30`
- `--fourcc MJPG`
- `--model ../../artifacts/models/tennis_ball_yolo/model.pt`
- `--conf 0.05`
- `--iou 0.5`
- `--imgsz 1280`
- `--max-detections 6`
- `--class-id 0`
- `--tile-width 2048`
- `--tile-height 1216`
- `--tile-overlap 160`
- `--display-width 720`
- `--warmup-frames 5`

小球在 4K 画面里太小时：

```bash
uv run --extra detect tennisbot-yolo detect-gui --tile
```

只查看解析后的配置，不打开相机：

```bash
uv run --extra detect tennisbot-yolo detect-gui --dry-run
```

退出 GUI：按 `q` 或 `Esc`。
