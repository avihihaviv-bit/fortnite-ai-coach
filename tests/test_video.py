import pytest

from fortnite_coach.core.errors import VideoError
from fortnite_coach.video.fingerprint import fingerprint
from fortnite_coach.video.frames import even_timestamps, extract_frames
from fortnite_coach.video.importer import import_video
from fortnite_coach.video.metadata import probe
from fortnite_coach.video.segments import coverage, plan_segments
from fortnite_coach.video.validator import validate_video_path


def test_validator_rejects_bad_inputs(tmp_path):
    with pytest.raises(VideoError) as e:
        validate_video_path(tmp_path / "match.replay")
    assert e.value.i18n_key == "video.err_replay"
    with pytest.raises(VideoError) as e:
        validate_video_path(tmp_path / "clip.avi")
    assert e.value.i18n_key == "video.err_format"
    with pytest.raises(VideoError) as e:
        validate_video_path(tmp_path / "missing.mp4")
    assert e.value.i18n_key == "video.err_missing"
    empty = tmp_path / "empty.mkv"
    empty.write_bytes(b"")
    with pytest.raises(VideoError) as e:
        validate_video_path(empty)
    assert e.value.i18n_key == "video.err_empty"


def test_all_supported_extensions_accepted(tmp_path):
    for ext in (".mp4", ".MOV", ".mkv", ".webm"):
        p = tmp_path / f"v{ext}"
        p.write_bytes(b"x")
        assert validate_video_path(p) == p


def test_probe_reads_real_metadata(sample_video):
    m = probe(sample_video)
    assert (m.width, m.height) == (640, 360)
    assert m.fps == 30
    assert 5.9 <= m.duration_s <= 6.1
    assert m.codec == "h264" and m.has_audio


def test_probe_rejects_garbage(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video" * 100)
    with pytest.raises(VideoError):
        probe(bad)


def test_fingerprint_stable_and_content_based(sample_video, tmp_path):
    assert fingerprint(sample_video) == fingerprint(sample_video)
    other = tmp_path / "other.mp4"
    other.write_bytes(sample_video.read_bytes() + b"x")
    assert fingerprint(other) != fingerprint(sample_video)


def test_frame_extraction(sample_video, tmp_path):
    ts = even_timestamps(6.0, 4)
    assert ts == [1.2, 2.4, 3.6, 4.8]
    frames = extract_frames(sample_video, ts, tmp_path / "f", max_width=320)
    assert len(frames) == 4 and all(f.stat().st_size > 0 for f in frames)


def test_segments_and_honest_coverage():
    segs = plan_segments(duration_s=700, segment_s=120, max_analyzed_s=300)
    assert [round(s.length_s) for s in segs] == [120, 120, 120, 120, 120, 100]
    assert [s.analyzed for s in segs] == [True, True, False, False, False, False]
    assert coverage(segs) == (240, 700)  # a partial segment is never silently cut
    assert plan_segments(0, 120, 300) == []
    # a short final segment must not be analyzed after a skipped one (no hidden gaps)
    tail = plan_segments(duration_s=400, segment_s=120, max_analyzed_s=300)
    assert [s.analyzed for s in tail] == [True, True, False, False]
    assert coverage(tail) == (240, 400)


def test_import_video_end_to_end(sample_video, tmp_path):
    v = import_video(sample_video, tmp_path / "frames")
    assert v.meta.width == 640 and len(v.thumbnails) == 4 and len(v.fingerprint) == 64
    again = import_video(sample_video, tmp_path / "frames")
    assert again.thumbnails == v.thumbnails  # thumbnails cached, not re-extracted
