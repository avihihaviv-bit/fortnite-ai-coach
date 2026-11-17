import time

import pytest

from fortnite_coach.config.settings import RecordingSettings
from fortnite_coach.recording import capabilities
from fortnite_coach.recording.command import build_command
from fortnite_coach.recording.hotkeys import HotkeyError, parse_hotkey
from fortnite_coach.recording.process_guard import parse_tasklist
from fortnite_coach.recording.recorder import Recorder, RecorderState, new_output_path
from fortnite_coach.video.ffmpeg_tools import find_ffmpeg
from fortnite_coach.video.metadata import probe

ENCODERS_SAMPLE = """Encoders:
 V..... = Video
 ------
 V....D libx264              libx264 H.264
 V....D h264_nvenc           NVIDIA NVENC H.264 encoder
 A....D aac                  AAC (Advanced Audio Coding)
"""


def test_parse_encoders():
    assert capabilities.parse_encoders(ENCODERS_SAMPLE) == ["libx264", "h264_nvenc"]


def test_parse_devices():
    out = " D  dshow           DirectShow capture\n D  gdigrab         GDI API Windows frame grabber\n"
    assert capabilities.parse_names(out, ("gdigrab", "dshow")) == {"gdigrab", "dshow"}


def test_listed_encoder_is_not_trusted_without_real_test():
    """On this test machine h264_nvenc is compiled into ffmpeg but there is no NVIDIA GPU:
    it must appear in built_encoders and NOT in working_encoders."""
    caps = capabilities.detect(find_ffmpeg())
    assert "libx264" in caps.working_encoders
    for enc in caps.working_encoders:
        assert capabilities.test_encoder(find_ffmpeg(), enc)
    if "h264_nvenc" in caps.built_encoders and not capabilities.test_encoder(find_ffmpeg(), "h264_nvenc"):
        assert "h264_nvenc" not in caps.working_encoders


def test_best_encoder_prefers_gpu():
    caps = capabilities.Capabilities(working_encoders=["libx264", "h264_amf", "h264_nvenc"], has_ddagrab=True)
    assert caps.best_encoder == "h264_nvenc" and caps.capture_backend == "ddagrab" and caps.can_record
    assert not capabilities.Capabilities(working_encoders=["libx264"]).can_record  # no capture backend


def test_command_nvenc_native_keeps_frames_on_gpu(tmp_path):
    plan = build_command("ffmpeg", "ddagrab", "h264_nvenc", RecordingSettings(), tmp_path / "o.mp4")
    a = " ".join(plan.args)
    assert "ddagrab=output_idx=0:framerate=60" in a and "h264_nvenc" in a
    assert "hwdownload" not in a  # no GPU->CPU copy
    assert "+frag_keyframe+empty_moov" in a  # crash-safe file
    assert "-f dshow" not in a  # video only by default


def test_command_scaling_and_audio(tmp_path):
    s = RecordingSettings(resolution="720p", fps=30, quality="high", audio_device="Stereo Mix (Realtek)")
    a = build_command("ffmpeg", "ddagrab", "h264_nvenc", s, tmp_path / "o.mp4").args
    joined = " ".join(a)
    assert "hwdownload,format=bgra,scale=1280:720" in joined
    assert "audio=Stereo Mix (Realtek)" in a and "aac" in a
    assert a[a.index("-cq") + 1] == "20"


def test_command_cpu_fallback(tmp_path):
    a = " ".join(build_command("ffmpeg", "gdigrab", "libx264", RecordingSettings(), tmp_path / "o.mp4").args)
    assert "-f gdigrab" in a and "ultrafast" in a and "yuv420p" in a
    with pytest.raises(ValueError):
        build_command("ffmpeg", "nope", "libx264", RecordingSettings(), tmp_path / "o.mp4")


def test_hotkey_parsing():
    assert parse_hotkey("Ctrl+Shift+F9") == (0x0002 | 0x0004, 0x78)
    assert parse_hotkey("alt+r") == (0x0001, ord("R"))
    for bad in ("F9", "Ctrl+", "Hyper+F9", "Ctrl+Shift+NotAKey"):
        with pytest.raises(HotkeyError):
            parse_hotkey(bad)


def test_fortnite_process_detection_parser():
    assert parse_tasklist('"FortniteClient-Win64-Shipping.exe","1234","Console","1","2,000,000 K"')
    assert not parse_tasklist('"explorer.exe","12","Console","1","100 K"')


def _test_plan(tmp_path, seconds=None):
    s = RecordingSettings(fps=30)
    return build_command(find_ffmpeg(), "test", "libx264", s, new_output_path(tmp_path / "rec"), test_duration_s=seconds)


def test_recorder_start_stop_produces_playable_file(tmp_path):
    rec = Recorder(tmp_path / "logs")
    plan = _test_plan(tmp_path)
    rec.start(plan)
    rec.start(plan)  # second press does nothing
    assert rec.is_recording
    time.sleep(2.5)
    out = rec.stop()
    assert rec.state is RecorderState.IDLE and out == plan.output
    meta = probe(out)
    assert meta.duration_s > 1.0 and meta.width == 640


def test_recorder_detects_process_exit(tmp_path):
    rec = Recorder(tmp_path / "logs")
    rec.start(_test_plan(tmp_path, seconds=1))
    deadline = time.time() + 15
    while rec.poll() is RecorderState.RECORDING and time.time() < deadline:
        time.sleep(0.2)
    assert rec.state is RecorderState.IDLE


def test_recorder_reports_ffmpeg_failure(tmp_path):
    rec = Recorder(tmp_path / "logs")
    plan = _test_plan(tmp_path)
    bad = plan.__class__(args=[*plan.args[:-1], "/nonexistent_dir/x.mp4"], output=plan.output, encoder="x", source="test")
    rec.start(bad)
    deadline = time.time() + 15
    while rec.poll() is RecorderState.RECORDING and time.time() < deadline:
        time.sleep(0.2)
    assert rec.state is RecorderState.FAILED and rec.error
