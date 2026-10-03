from app.formats import parse_inline_point_timeline, parse_txt


def test_inline_point_timeline_ignores_header_and_splits():
    text = "檔名 逐字稿 辨識引擎：混合模式 [00:00:00] 第一段。第二句！ [00:00:30] 接下來內容。"
    tr = parse_inline_point_timeline(text, "demo", "DOCX")
    assert tr is not None
    assert tr.timed is True
    assert tr.estimated is True
    assert len(tr.segments) >= 3
    assert all("辨識引擎" not in s.text for s in tr.segments)
    assert tr.segments[0].start == 0
    assert tr.segments[-1].start >= 30


def test_parse_txt_inline_markers_are_timed():
    tr = parse_txt("[00:00:10] 甲。乙。 [00:00:20] 丙。", "x")
    assert tr.timed
    assert tr.estimated
    assert tr.segments[0].start == 10
    assert tr.segments[-1].start >= 20
