# TennisBot Recording Tool

`tools/recording` migrates the local V4L2/ffmpeg scripts from `~/Codes/record`
into a uv-managed CLI.

## Config

Default config:

```bash
tools/recording/configs/tennis_camera_recording.yaml
```

The config stores 4K MJPEG capture defaults and V4L2 controls such as
`exposure_time_absolute`, fixed white balance, brightness, gain, sharpness, and
focus mode. Relative output paths are resolved from the repository root.

Inspect the parsed config:

```bash
uv run tennisbot-recording config show
```

## Recording

From this directory:

```bash
uv run tennisbot-recording record single --dry-run
uv run tennisbot-recording record single --duration 60
uv run tennisbot-recording record single --duration 60 --sample-fps 3
uv run tennisbot-recording record dual --dry-run
uv run tennisbot-recording record dual --duration 60
uv run tennisbot-recording record dual --preview
uv run tennisbot-recording gui single
```

From the repository root, prefer the wrapper:

```bash
uv run scripts/recording.py single --dry-run
uv run scripts/recording.py dual --duration 60
uv run scripts/recording.py gui
```

Both `single` and `dual` configure the selected cameras before recording. CLI
control flags override the YAML for one run:

```bash
uv run scripts/recording.py single --exposure 100 --wb 4600 --duration 30
uv run scripts/recording.py dual --control exposure_time_absolute=166
```

Default outputs are written under ignored `runs/recording`.

## Postprocessing

Extract videos into the YOLO annotation image layout:

```bash
uv run scripts/recording.py extract --dry-run 20260701_205507
uv run scripts/recording.py extract --fps 2 runs/recording/20260701_205507
```

Normalize videos whose packet timestamps are absolute Unix times:

```bash
uv run scripts/recording.py normalize --dry-run --base-epoch 1782893181 runs/recording/20260701_205507
uv run scripts/recording.py normalize --output-dir fixed runs/recording/20260701_205507
```

Soft sync is still software timestamp normalization. It is not hardware sync.
