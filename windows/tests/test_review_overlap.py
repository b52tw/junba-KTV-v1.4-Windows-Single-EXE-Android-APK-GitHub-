from app.models import Segment, TextTrack
from app.review import compare_tracks, similarity


def test_overlap_merges_multiple_segments():
    base = TextTrack('base', [Segment(0, 4, '今天討論績效管理以及後續安排')], timed=True)
    other = TextTrack('other', [Segment(0, 2, '今天討論績效管理'), Segment(2, 4, '以及後續安排')], timed=True)
    r = compare_tracks(base, other)[0]
    assert r.level == 'green'
    assert '後續安排' in r.other_text


def test_speaker_prefix_is_ignored():
    assert similarity('spk:0：今天討論績效', '今天討論績效') > .95


def test_same_track_is_green():
    t = TextTrack('same', [Segment(0, 2, '內容')], timed=True)
    assert compare_tracks(t, t)[0].score == 1.0
