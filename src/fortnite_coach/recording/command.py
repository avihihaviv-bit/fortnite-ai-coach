"""Build the ffmpeg command line for a recording.

Capture sources:
- ddagrab  : Windows Desktop Duplication API. Frames stay on the GPU, so with a
             GPU encoder (NVENC/AMF) the CPU barely touches the frames.
- gdigrab  : fallback when ddagrab is unavailable. More CPU work.
- test     : synthetic source used by automated tests (never shown to users).

Output is fragmented MP4: if the app or PC crashes mid-recording, the file
written so far is still playable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fortnite_coach.config.settings import RecordingSettings

RESOLUTIONS = {"1440p": (2560, 1440), "1080p": (1920, 1080), "720p": (1280, 720)}

# Constant-quality targets (lower = better quality, bigger files).
QUALITY = {
    "nvenc": {"low": 30, "medium": 25, "high": 20},
    "amf": {"low": 30, "medium": 25, "high": 20},
    "qsv": {"low": 30, "medium": 25, "high": 20},
    "x264": {"low": 28, "medium": 23, "high": 19},
}


@dataclass(frozen=True)
class RecordingPlan:
    args: list[str]
    output: Path
    encoder: str
    source: str


def _family(encoder: str) -> str:
    if "nvenc" in encoder:
        return "nvenc"
    if "amf" in encoder:
        return "amf"
    if "qsv" in encoder:
        return "qsv"
    return "x264"


def encoder_args(encoder: str, quality: str, fps: int) -> list[str]:
    fam = _family(encoder)
    q = str(QUALITY[fam][quality])
    gop = str(fps * 2)  # keyframe every 2 s -> fragments flush regularly
    if fam == "nvenc":
        return ["-c:v", encoder, "-preset", "p4", "-tune", "ll", "-rc", "vbr", "-cq", q, "-b:v", "0", "-g", gop]
    if fam == "amf":
        return ["-c:v", encoder, "-usage", "lowlatency", "-rc", "cqp", "-qp_i", q, "-qp_p", q, "-g", gop]
    if fam == "qsv":
        return ["-c:v", encoder, "-preset", "veryfast", "-global_quality", q, "-g", gop]
    return ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-crf", q, "-g", gop, "-pix_fmt", "yuv420p"]


def build_command(
    ffmpeg: str, source: str, encoder: str, settings: RecordingSettings, output: Path,
    *, test_duration_s: float | None = None,
) -> RecordingPlan:
    fps = settings.fps
    fam = _family(encoder)
    target = RESOLUTIONS.get(settings.resolution)
    args = [ffmpeg, "-hide_banner", "-loglevel", "warning", "-y"]
    vf: list[str] = []

    if source == "ddagrab":
        args += ["-f", "lavfi", "-i", f"ddagrab=output_idx={settings.monitor_index}:framerate={fps}:draw_mouse=0"]
        gpu_direct = fam in ("nvenc", "amf") and target is None
        if not gpu_direct:
            vf += ["hwdownload", "format=bgra"]  # bring frames to system memory for scaling / CPU encoders
    elif source == "gdigrab":
        args += ["-f", "gdigrab", "-framerate", str(fps), "-draw_mouse", "0", "-i", "desktop"]
    elif source == "test":
        args += ["-re", "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate={fps}"]
        if test_duration_s:
            args += ["-t", str(test_duration_s)]
    else:
        raise ValueError(f"unknown capture source {source}")

    if settings.audio_device and source in ("ddagrab", "gdigrab"):
        args += ["-f", "dshow", "-i", f"audio={settings.audio_device}"]

    if target:
        vf.append(f"scale={target[0]}:{target[1]}:force_original_aspect_ratio=decrease")
    if fam in ("x264", "qsv") or (vf and source == "ddagrab"):
        vf.append("format=yuv420p" if fam == "x264" else "format=nv12")
    if vf:
        args += ["-vf", ",".join(vf)]

    args += encoder_args(encoder, settings.quality, fps)
    if settings.audio_device and source in ("ddagrab", "gdigrab"):
        args += ["-c:a", "aac", "-b:a", "160k"]
    args += ["-movflags", "+frag_keyframe+empty_moov+default_base_moof", str(output)]
    return RecordingPlan(args=args, output=output, encoder=encoder, source=source)
