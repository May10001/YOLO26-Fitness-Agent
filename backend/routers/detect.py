import base64
import asyncio
from pathlib import Path
import numpy as np
import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import load_api_config

router = APIRouter()
_detector = None

# Shorter system prompt for proactive coaching pushes (from code/coach_system_prompt.py)
COACH_PROACTIVE_SYSTEM = (
    "你是一名资深健身教练，正在通过计算机视觉实时观察用户训练。"
    "根据系统推送的实时训练数据，给出1-3句话的专业指导。"
    "优先关注安全问题，错误纠正要具体可操作，语气鼓励但不夸张。"
    "用中文回答。"
)


def get_detector():
    global _detector
    if _detector is None:
        from ..services.detector import DetectorService
        _detector = DetectorService()
    return _detector


async def _send_proactive_coach(ws: WebSocket, trigger_context: str):
    """Call DashScope API with proactive coach context, send result as 'coach' message."""
    config = load_api_config()
    if not config.get("use_remote") or not config.get("api_key"):
        # Silently skip — no API configured for proactive coaching
        return

    try:
        from openai import OpenAI

        def _call_api():
            client = OpenAI(
                api_key=config["api_key"],
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            completion = client.chat.completions.create(
                model=config.get("model_code", "qwen-plus"),
                messages=[
                    {"role": "system", "content": COACH_PROACTIVE_SYSTEM},
                    {"role": "user", "content": trigger_context},
                ],
                temperature=0.7,
                max_tokens=300,
            )
            return completion.choices[0].message.content

        # Run synchronous API call in thread pool to avoid blocking the event loop
        reply = await asyncio.get_event_loop().run_in_executor(None, _call_api)
        await ws.send_json({"type": "coach", "text": reply, "trigger": "proactive"})
    except Exception:
        pass  # Proactive coach failure should not break the detection loop


def _decode_frame(b64data: str):
    """Decode a base64 JPEG frame to numpy array."""
    img_bytes = base64.b64decode(b64data)
    nparr = np.frombuffer(img_bytes, np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)


@router.websocket("/ws/detect")
async def websocket_detect(ws: WebSocket):
    await ws.accept()
    detector = get_detector()

    # Single-slot queue: new frames replace old ones, so the processor
    # always works on the latest available frame. This prevents the
    # skeleton overlay from lagging behind the user's movement.
    frame_queue: asyncio.Queue = asyncio.Queue(maxsize=1)

    async def process_frames():
        """Consume frames from queue at the backend's natural speed."""
        while True:
            b64data = await frame_queue.get()
            frame = _decode_frame(b64data)
            result = detector.process_frame(frame)
            await ws.send_json({"type": "result", **result})

            trigger_context = result.pop("trigger_context", None)
            if trigger_context:
                asyncio.create_task(_send_proactive_coach(ws, trigger_context))

    processor = asyncio.create_task(process_frames())

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
                # Replace stale frame with latest — queue maxsize=1 handles this
                if frame_queue.full():
                    try:
                        frame_queue.get_nowait()  # discard old frame
                    except asyncio.QueueEmpty:
                        pass
                await frame_queue.put(data["data"])

    except WebSocketDisconnect:
        processor.cancel()
