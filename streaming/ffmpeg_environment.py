"""Control the configuration inherited by FFmpeg subprocesses."""

import os


def ffmpeg_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("RTSP_", "STREAMING_"))
        and key.upper() != "FFREPORT"
    }
