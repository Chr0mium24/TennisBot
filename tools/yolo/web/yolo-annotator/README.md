# YOLO Annotator

Static frontend for the local tennis ball YOLO label tool.

Run the backend from the repository root:

```sh
uv run tennisbot-yolo annotate
```

Then open `http://127.0.0.1:8765`.

The page can still be opened directly in Chrome or Edge as a fallback, but the
backend mode is preferred because it writes labels and `excluded_images.txt`
reliably.
