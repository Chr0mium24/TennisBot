# YOLO 标注、抠球审核和数据增强使用说明

日期：2026-07-03

## 目标

这套流程用于从已标注的 YOLO bbox 中抠出网球 sprite，人工审核 mask 后，
再把审核通过的球贴到背景图上生成新的 YOLO detect 训练样本。

核心约束：

- 原始人工标注仍然是 YOLO bbox。
- 抠球审核页只编辑 ellipse/alpha mask，不改原始 bbox label。
- `sprites extract` 默认不会覆盖已编辑候选，只有加 `--overwrite` 才会重写。
- `approved/` 和 `rejected/` 目录不会被 `sprites extract` 修改。
- 增强输出写到 `tools/yolo/yolo/runs/`，不覆盖原始图片和标签。
- 原始数据文件不被改写；生成增强图时可以对整张输出图做轻微旋转，并会重算全部 bbox。
- 增强输出仍然使用普通水平 YOLO bbox，不写旋转框。

## 当前 0260701 数据集流程

当前本地图片目录：

```text
tools/yolo/0260701/images
```

建议标签目录：

```text
tools/yolo/0260701/labels
```

### 1. 启动 bbox 标注页面

局域网验证时监听 `0.0.0.0`：

```bash
bun scripts/yolo.ts annotate \
  --images-root tools/yolo/0260701/images \
  --labels-root tools/yolo/0260701/labels \
  --excluded-file tools/yolo/0260701/excluded_images.txt \
  --host 0.0.0.0 \
  --port 8765
```

打开：

```text
http://<机器IP>:8765
```

本机也可以用：

```text
http://127.0.0.1:8765
```

在页面里用 bbox 标注网球。保存后会写入：

```text
tools/yolo/0260701/labels/<image-stem>.txt
```

### 2. 从 bbox 生成球 sprite 候选

标完若干张后运行：

```bash
bun scripts/yolo.ts sprites extract \
  --images-root tools/yolo/0260701/images \
  --labels-root tools/yolo/0260701/labels \
  --excluded-file tools/yolo/0260701/excluded_images.txt
```

默认输出：

```text
tools/yolo/yolo/runs/sprites/candidates/
tools/yolo/yolo/runs/sprites/manifest.jsonl
```

不要加 `--overwrite`，这样已经生成并编辑过的候选不会被重写。
只有确认要重新按 bbox 初始化 mask 时才使用：

```bash
bun scripts/yolo.ts sprites extract ... --overwrite
```

### 3. 启动球 sprite 审核页面

```bash
bun scripts/yolo.ts sprites review \
  --host 0.0.0.0 \
  --port 8766
```

打开：

```text
http://<机器IP>:8766
```

审核页面功能：

- 左侧选择候选 sprite。
- 中间查看原图 crop 和绿色 ellipse/mask overlay。
- 右侧调整 `Center X/Y`、`Radius X/Y`、`Rotation`、`Feather`。
- `Save` 保存当前 mask。
- `Approve` 保存并复制到 approved。
- `Reject` 保存并复制到 rejected。

审核通过输出：

```text
tools/yolo/yolo/runs/sprites/approved/
```

拒绝输出：

```text
tools/yolo/yolo/runs/sprites/rejected/
```

### 4. 准备 0260701 的增强配置

默认配置 `tools/yolo/configs/augmentation.toml` 面向默认 dataset：

```text
tools/yolo/yolo/dataset
```

如果要对 `0260701` 直接做增强，建议把临时配置放到 ignored 的 runs 目录：

```bash
mkdir -p tools/yolo/yolo/runs
cp tools/yolo/configs/augmentation.toml tools/yolo/yolo/runs/augmentation.0260701.toml
```

把 `tools/yolo/yolo/runs/augmentation.0260701.toml` 里的输入和输出改成：

```toml
[inputs]
dataset_root = "tools/yolo/0260701"
sprites_root = "tools/yolo/yolo/runs/sprites/approved"
excluded_file = "tools/yolo/0260701/excluded_images.txt"

[output]
root = "tools/yolo/yolo/runs/copy_paste_aug_0260701"
count = 1000
seed = 42
image_format = "jpg"
jpeg_quality = 92
```

其它参数可以先保持默认。

常用增强参数：

```toml
[frame]
rotate_probability = 0.35
rotate_degrees = [-2.0, 2.0]

[ball]
scale = [0.6, 1.8]
stretch_x = [0.9, 1.1]
stretch_y = [0.9, 1.1]
rotate_degrees = [-180, 180]
```

说明：

- `frame.rotate_degrees` 是整张生成图的轻微旋转，用来模拟相机滚转/抖动。
- 整图旋转后，所有原始 bbox 和新贴球 bbox 都会用四角变换重新取水平外接框。
- `ball.stretch_x/stretch_y` 是球 sprite 的轻微拉伸，模拟运动拖影和成像变形。
- `ball.rotate_degrees` 只旋转贴上去的球 sprite，可以用较大范围模拟不同拖影方向。
- 这些参数不要开太大；整图旋转过大会让水平 bbox 明显变松。

### 5. 生成增强数据集

确认 `approved/` 里已经有审核通过的 sprite 后运行：

```bash
bun scripts/yolo.ts augment copy-paste \
  --config tools/yolo/yolo/runs/augmentation.0260701.toml
```

输出目录：

```text
tools/yolo/yolo/runs/copy_paste_aug_0260701/
  data.yaml
  train.txt
  val.txt
  images/
  labels/
  manifest.jsonl
  config.resolved.toml
  report.md
```

说明：

- `val.txt` 为空，第一版不生成合成验证集。
- 如果背景图已有原始 bbox label，会先载入原 label；若整图旋转启用，则原 label 也会被旋转重算。
- 如果背景图是空 label 或未标注图，会只写入贴上去的球 bbox。
- 贴上去的球 bbox 根据最终 alpha mask 水平外接框生成，不沿用原 bbox。

## 常用检查命令

查看当前有多少 label：

```bash
find tools/yolo/0260701/labels -type f -name '*.txt' | wc -l
```

查看非空正样本 label 数：

```bash
find tools/yolo/0260701/labels -type f -name '*.txt' \
  -exec sh -c 'for f do [ -s "$f" ] && printf "%s\n" "$f"; done' sh {} + | wc -l
```

查看候选 sprite：

```bash
find tools/yolo/yolo/runs/sprites/candidates -maxdepth 1 -type f | sort
```

查看审核通过 sprite：

```bash
find tools/yolo/yolo/runs/sprites/approved -maxdepth 1 -type f | sort
```

查看增强结果报告：

```bash
sed -n '1,120p' tools/yolo/yolo/runs/copy_paste_aug_0260701/report.md
```

## 注意事项

- `tools/yolo/0260701/` 是本地数据目录，当前未纳入 Git。
- `tools/yolo/yolo/runs/` 是生成输出目录，已被 `tools/yolo/.gitignore` 忽略。
- 不要把合成数据直接当验证集用；验证必须保留真实未增强样本。
- 只有训练和验证实验完成后，才能声明模型效果提升。
