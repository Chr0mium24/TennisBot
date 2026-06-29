# 模型 artifact 上传结果

日期：2026-06-29

## 结果

当前可用 YOLO 运行时模型包已纳入 Git 跟踪范围：

```text
artifacts/models/tennis_ball_yolo/
```

`.gitignore` 仍然忽略其它 `artifacts/` 内容，只放行这个模型包目录。

## 模型包内容

- `model.pt`: 5,450,181 bytes
- `model.onnx`: 10,261,007 bytes
- `package.json`
- `metadata.json`
- `labels.json`
- `preprocessing.json`
- `postprocessing.json`
- `eval_report.md`
- `eval_metrics.json`
- `package_manifest.json`

## 合同状态

`package.json` 显示：

- `dry_run`: false
- `inference_ready`: true
- `default_model`: onnx
- `models`: pt, onnx

## 验证

```bash
cd tools/yolo
uv run --no-sync tennisbot-yolo package verify
```

结果：

```text
verified=/home/cr/Codes/TennisBot/artifacts/models/tennis_ball_yolo
```
