"""Entrega fotogramas nuevos y atiende los controles de la vista en vivo."""

import time
from collections.abc import Iterator

import cv2
import numpy as np

from rtsp.latest_frame import FramePacket, LatestFrameCapture


def preview_frames(
    capture: LatestFrameCapture, window_name: str,
) -> Iterator[FramePacket]:
    no_video = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(
        no_video, "Sin video RTSP", (24, 60),
        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2,
    )
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.imshow(window_name, no_video)
    showing_video = False
    last_sequence = None

    while cv2.waitKey(1) & 0xFF != ord("q"):
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            break
        packet = capture.read_latest()
        if packet is None and showing_video:
            cv2.imshow(window_name, no_video)
            showing_video = False
        if packet is None or packet.sequence == last_sequence:
            time.sleep(0.005)
            continue
        last_sequence = packet.sequence
        yield packet
        showing_video = True
