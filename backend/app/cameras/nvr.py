"""NVR support: an NVR is N logical RTSP cameras, one per channel.

No NVR-specific giant subsystem: channel expansion produces ordinary camera
definitions (source_type=rtsp + channel URL), each with independent camera_id,
health, and reconnect lifecycle downstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NvrChannel:
    channel: int
    name: str = ""
    url: str = ""  # fully-formed RTSP URL for this channel (may embed credentials)


@dataclass
class NvrSpec:
    name: str
    host: str
    username: str = ""
    password: str = ""  # server-side only; never logged or returned
    channels: list[NvrChannel] = field(default_factory=list)
    url_template: str = "rtsp://{user}:{password}@{host}:554/Streaming/Channels/{ch}01"


def expand_nvr_channels(spec: NvrSpec, user_id: str) -> list[dict]:
    """Expand an NVR spec into per-channel camera definitions.

    Channels with an explicit url keep it; others are built from url_template.
    Returns dicts ready for CameraRepository.create (name/source_type/config).
    """
    out: list[dict] = []
    for ch in spec.channels:
        url = ch.url or spec.url_template.format(
            user=spec.username, password=spec.password, host=spec.host, ch=ch.channel
        )
        label = ch.name or f"{spec.name} ch{ch.channel}"
        out.append(
            {
                "name": label,
                "source_type": "rtsp",
                "config": {
                    "url": url,
                    "nvr": spec.name,
                    "channel": ch.channel,
                },
            }
        )
    return out
