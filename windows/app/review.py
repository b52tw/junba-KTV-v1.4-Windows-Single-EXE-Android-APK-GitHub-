from __future__ import annotations
import re
from difflib import SequenceMatcher
from dataclasses import dataclass
from .models import Segment, TextTrack

_SPEAKER_PREFIX_RE = re.compile(
    r'^\s*(?:(?:spk|speaker)\s*[:#-]?\s*\d+|(?:講者|說話者)\s*\d+)\s*[：:]\s*',
    re.I,
)


def normalize_text(text: str) -> str:
    text = (text or '').lower()
    text = _SPEAKER_PREFIX_RE.sub('', text)
    text = re.sub(r'[\s\u3000]+', '', text)
    text = re.sub(r'[，。！？；：、,.!?;:"“”‘’()（）\[\]【】<>《》…—\-]+', '', text)
    return text


def similarity(a: str, b: str) -> float:
    a = normalize_text(a); b = normalize_text(b)
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _time_window(seg: Segment) -> tuple[float, float]:
    start = float(seg.start)
    end = float(seg.end if seg.end > seg.start else seg.start + 0.8)
    return start, end


def find_time_text(seg: Segment, track: TextTrack, tolerance: float = 0.35) -> str:
    """Return all comparison text that overlaps the base segment.

    Older builds matched only one segment by midpoint. When the two tracks used
    different sentence splitting, that created many false red / "missing" rows.
    This version merges every comparison segment that overlaps the same time
    window (with a small tolerance), so 1-to-many and many-to-1 segmentation is
    compared as one passage.
    """
    if not track.segments:
        return ''
    a0, a1 = _time_window(seg)
    hits = []
    for other in track.segments:
        b0, b1 = _time_window(other)
        overlap = min(a1 + tolerance, b1 + tolerance) - max(a0 - tolerance, b0 - tolerance)
        if overlap > 0:
            hits.append(other)
    if hits:
        hits.sort(key=lambda x: (x.start, x.end))
        return ' '.join(x.text.strip() for x in hits if x.text.strip()).strip()
    mid = (a0 + a1) / 2
    nearest = min(track.segments, key=lambda x: abs(float(x.start) - mid))
    return nearest.text.strip()


@dataclass
class ReviewResult:
    index: int
    score: float
    level: str
    other_text: str
    note: str


def compare_tracks(base: TextTrack, other: TextTrack, good: float = .82, warn: float = .55) -> list[ReviewResult]:
    out: list[ReviewResult] = []
    if base is other:
        return [ReviewResult(i, 1.0, 'green', s.text, '同一文字軌') for i, s in enumerate(base.segments)]
    for i, seg in enumerate(base.segments):
        other_text = find_time_text(seg, other)
        if not other_text:
            out.append(ReviewResult(i, 0.0, 'red', '', '找不到同時間文字'))
            continue
        score = similarity(seg.text, other_text)
        level = 'green' if score >= good else ('yellow' if score >= warn else 'red')
        note = '高度吻合' if level == 'green' else ('內容接近，建議聽音核對' if level == 'yellow' else '文字差異較大；不等於一定漏字')
        out.append(ReviewResult(i, score, level, other_text, note))
    return out
