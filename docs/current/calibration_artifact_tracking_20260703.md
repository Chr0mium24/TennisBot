# Calibration Artifact Tracking

日期：2026-07-03

## 目标

把当前运行时需要的相机标定参数纳入 Git，避免拉取仓库后缺少
`artifacts/calibration/stereo_cam1_cam2` 导致视觉运行时无法加载标定包。

## 计划

1. 只放开已验收的运行时标定包：
   - `artifacts/calibration/cam1`
   - `artifacts/calibration/cam2`
   - `artifacts/calibration/stereo_cam1_cam2`
2. 继续忽略原始采集帧、实验图片、候选模型和 dry-run 标定输出。
3. 提交标定包内的小型 JSON/YAML/Markdown/HTML 报告文件，不提交采集视频或图片。

## 结果

- `.gitignore` 已允许 Git 跟踪当前三个运行时标定包。
- `artifacts/calibration_sessions/` 和 `artifacts/calibration_experiments/` 仍保持忽略。
- 标定包中的来源路径已改成仓库相对路径，避免提交本机绝对路径。
- 当前 stereo 包状态：
  - `accepted: true`
  - `dry_run: false`
  - `hardware_validated: true`
  - `baseline_m: 0.1649889033601914`
  - `stereo_rms_reprojection_px: 0.21213797585745228`
  - `epipolar_rms_px: 0.2567744520215293`

## 验证结果

```bash
git check-ignore -v artifacts/calibration/stereo_cam1_cam2/package.json
cd tools/calibration && uv run pytest -q
```

- 标定包命中 `.gitignore` 的取消忽略规则，可以被 Git 跟踪。
- 采集帧和实验输出仍命中 `artifacts/*` 忽略规则。
- 标定包 JSON 文件解析通过。
- 标定包内没有 `/home/cr` 或 `Codes/TennisBot` 绝对路径残留。
- `tools/calibration` 测试结果：`21 passed in 0.32s`。
