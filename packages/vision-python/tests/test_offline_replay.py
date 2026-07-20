from tennisbot_vision.offline_replay import trajectory_prediction_text_anchors


def test_trajectory_prediction_text_stays_out_of_diagnostics_panel() -> None:
    anchors = trajectory_prediction_text_anchors(image_width=1880, image_height=404, panel_width=440)
    diagnostics_panel_left = 1880 - 440

    assert anchors
    assert max(anchor.x for anchor in anchors) < diagnostics_panel_left
    assert [anchor.y for anchor in anchors] == sorted(anchor.y for anchor in anchors)
