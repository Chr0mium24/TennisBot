# Camera Devices

Date: 2026-07-19

The canonical mapping is cam1/left `/dev/video0` and cam2/right
`/dev/video2`. Inspect the host with:

```bash
uv run scripts/camera.py list
uv run scripts/camera.py check
uv run scripts/camera.py controls show stereo
```

Raw preview:

```bash
uv run scripts/camera.py preview cam1
uv run scripts/camera.py preview cam2
uv run scripts/camera.py preview stereo
```

Apply profiles before a manual workflow when needed:

```bash
uv run scripts/camera.py controls apply stereo --profile runtime
uv run scripts/camera.py controls apply stereo --profile recording
uv run scripts/camera.py controls apply stereo --profile calibration
```

Do not infer left/right from USB enumeration in another command. Change the
canonical configuration if deployment identities differ.
