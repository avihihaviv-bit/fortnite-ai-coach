"""Detect what this machine can actually record with.

An encoder appearing in `ffmpeg -encoders` only means ffmpeg was BUILT with it
(e.g. h264_nvenc is listed even without an NVIDIA GPU). We therefore run a tiny
real test encode before declaring an encoder available.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

from fortnite_coach.video.ffmpeg_tools import run

# Preference order: GPU encoders first (lowest CPU/FPS cost), CPU x264 last.
ENCODER_PREFERENCE = ("h264_nvenc", "hevc_nvenc", "h264_amf", "h264_qsv", "libx264")
HARDWARE_ENCODERS = frozenset({"h264_nvenc", "hevc_nvenc", "h264_amf", "h264_qsv"})


@dataclass
class Capabilities:
    ffmpeg_version: str = ""
    built_encoders: list[str] = field(default_factory=list)   # compiled in
    working_encoders: list[str] = field(default_factory=list)  # passed a real test encode
    has_ddagrab: bool = False   # Desktop Duplication capture (Windows 8+, frames stay on GPU)
    has_gdigrab: bool = False   # GDI capture (fallback, CPU heavy)
    has_dshow: bool = False     # DirectShow (audio devices)

    @property
    def best_encoder(self) -> str | None:
        return next((e for e in ENCODER_PREFERENCE if e in self.working_encoders), None)

    @property
    def capture_backend(self) -> str | None:
        if self.has_ddagrab:
            return "ddagrab"
        if self.has_gdigrab:
            return "gdigrab"
        return None

    @property
    def can_record(self) -> bool:
        return self.capture_backend is not None and self.best_encoder is not None


def parse_encoders(output: str) -> list[str]:
    names = []
    for line in output.splitlines():
        parts = line.split()
        # skip the legend ("V..... = Video") - real rows have an encoder name, not "="
        if len(parts) >= 2 and len(parts[0]) == 6 and parts[0][0] == "V" and parts[1] != "=":
            names.append(parts[1])
    return names


def parse_names(output: str, wanted: tuple[str, ...]) -> set[str]:
    found = set()
    for line in output.splitlines():
        parts = line.split()
        for w in wanted:
            if w in parts:
                found.add(w)
    return found


def test_encoder(ffmpeg: str, encoder: str, timeout: float = 20) -> bool:
    """Encode a few synthetic frames; True only if the hardware/driver really works."""
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=30",
            "-frames:v", "10", "-c:v", encoder, "-f", "null", "-"]
    try:
        return run(args, timeout=timeout).returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def detect(ffmpeg: str) -> Capabilities:
    caps = Capabilities()
    ver = run([ffmpeg, "-hide_banner", "-version"], timeout=15)
    caps.ffmpeg_version = (ver.stdout.splitlines() or [""])[0]
    caps.built_encoders = [e for e in parse_encoders(run([ffmpeg, "-hide_banner", "-encoders"], timeout=15).stdout)
                           if e in ENCODER_PREFERENCE]
    caps.working_encoders = [e for e in ENCODER_PREFERENCE if e in caps.built_encoders and test_encoder(ffmpeg, e)]
    caps.has_ddagrab = "ddagrab" in parse_names(run([ffmpeg, "-hide_banner", "-filters"], timeout=15).stdout, ("ddagrab",))
    devices = parse_names(run([ffmpeg, "-hide_banner", "-devices"], timeout=15).stdout, ("gdigrab", "dshow"))
    caps.has_gdigrab = "gdigrab" in devices
    caps.has_dshow = "dshow" in devices
    return caps


def list_dshow_audio_devices(ffmpeg: str) -> list[str]:
    """Windows only. ffmpeg prints devices on stderr: `"Name" (audio)`."""
    res = run([ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"], timeout=15)
    out = []
    for line in res.stderr.splitlines():
        if "(audio)" in line and '"' in line:
            out.append(line.split('"')[1])
    return out
