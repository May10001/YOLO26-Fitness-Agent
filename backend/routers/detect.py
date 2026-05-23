import base64
import numpy as np
import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
_detector = None


def get_detector():
    global _detector
    if _detector is None:
        from ..services.detector import DetectorService
        _detector = DetectorService()
    return _detector


@router.websocket("/ws/detect")
async def websocket_detect(ws: WebSocket):
    await ws.accept()
    detector = get_detector()
    try:
        while True:
            data = await ws.receive_json()

            if data.get("type") == "set_exercise":
                detector.set_exercise(data["exercise"])
                await ws.send_json({"type": "exercise_set", "exercise": data["exercise"]})
                continue

            if data.get("type") == "reset":
                detector.reset()
                await ws.send_json({"type": "reset_done"})
                continue

            if data.get("type") == "frame":
                img_bytes = base64.b64decode(data["data"])
                nparr = np.frombuffer(img_bytes, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                result = detector.process_frame(frame)
                await ws.send_json({"type": "result", **result})

    except WebSocketDisconnect:
        pass
