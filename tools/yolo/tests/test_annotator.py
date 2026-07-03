from __future__ import annotations

from pathlib import Path

from tennisbot_yolo.annotator import build_video_summaries, create_app, image_entries, write_excluded_paths


def test_annotator_indexes_labels_and_exclusions(tmp_path: Path) -> None:
    images_root = tmp_path / "images"
    labels_root = tmp_path / "labels"
    excluded_file = tmp_path / "excluded_images.txt"
    (images_root / "session").mkdir(parents=True)
    (labels_root / "session").mkdir(parents=True)
    (images_root / "session" / "clip_cam1_frame_000001.jpg").write_bytes(b"fake")
    (images_root / "session" / "clip_cam1_frame_000002.jpg").write_bytes(b"fake")
    (labels_root / "session" / "clip_cam1_frame_000001.txt").write_text(
        "0 0.5 0.5 0.1 0.1\n",
        encoding="utf-8",
    )
    (labels_root / "session" / "clip_cam1_frame_000002.txt").write_text("", encoding="utf-8")
    write_excluded_paths(excluded_file, {"session/clip_cam1_frame_000002.jpg"})

    entries = image_entries(images_root, labels_root, excluded_file)
    summaries = build_video_summaries(images_root, labels_root, excluded_file)
    app = create_app(images_root, labels_root, tmp_path / "index.html", excluded_file)

    assert [entry["label_status"] for entry in entries] == ["ball", "empty"]
    assert entries[1]["excluded"] is True
    assert summaries[0]["id"] == "clip"
    assert summaries[0]["labeled"] == 2
    assert summaries[0]["ball"] == 1
    assert summaries[0]["empty"] == 1
    assert summaries[0]["excluded"] == 1
    assert {route.path for route in app.routes} >= {"/api/health", "/api/images", "/api/videos"}
