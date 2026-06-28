# Wave 6 YOLO Tool Runtime Results

Date: 2026-06-29

## Scope

Implemented the standalone `tools/yolo` Python package for runtime model
package creation and verification. This wave does not train YOLO, run
inference, scan datasets, or modify `TennisBallDetectorLab`.

## Commands

```bash
cd tools/yolo
uv sync
uv run pytest -q
uv run tennisbot-yolo --help
uv run tennisbot-yolo package create --output-dir ../../artifacts/models/tennis_ball_yolo --dry-run
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
cd ../..
git diff --check
git diff --name-only main..HEAD
```

## Result

- `uv sync`: passed.
- `uv run pytest -q`: passed with 12 tests after lead review.
- `uv run tennisbot-yolo --help`: passed and exposed `package`.
- `uv run tennisbot-yolo package create --output-dir ../../artifacts/models/tennis_ball_yolo --dry-run`: passed.
- `uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo`: passed.
- `git diff --check`: passed.

Generated dry-run outputs are under ignored `artifacts/` and are not intended
for commit.

Lead review tightened package verification to check every declared model entry,
not only the default model, and to reject boolean values where numeric model
byte counts or preprocessing sizes are required.

After merge, the generated dry-run package was loaded through `packages/core`'s
`loadYoloModelArtifactMetadata` helper. The smoke check returned
`selectedModel: onnx`, `modelPath: model.onnx`, and three pending model checks,
confirming the package metadata is consumable by the runtime loader.
