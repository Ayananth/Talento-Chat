from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from typing import Dict, List
from app.auth import decode_jwt

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        # room_id -> list of (websocket, user_id)
        self.rooms: Dict[str, List[tuple[WebSocket, str]]] = {}

    async def connect(self, room_id: str, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.rooms.setdefault(room_id, []).append((websocket, user_id))
        print(f"User {user_id} joined room {room_id}")

    def disconnect(self, room_id: str, websocket: WebSocket):
        self.rooms[room_id] = [
            (ws, uid) for ws, uid in self.rooms[room_id] if ws != websocket
        ]

        if not self.rooms[room_id]:
            del self.rooms[room_id]

    async def broadcast(self, room_id: str, message: dict):
        for ws, _ in self.rooms.get(room_id, []):
            await ws.send_json(message)

manager = ConnectionManager()

@app.get("/")
def root():
    return {"message": "FastAPI is running"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"Message: {data}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.websocket("/ws/chat/{conversation_id}")
async def websocket_chat(
    websocket: WebSocket,
    conversation_id: str,
    token: str = Query(...)
):
    payload = decode_jwt(token)

    if not payload:
        await websocket.close(code=1008)
        return

    user_id = str(payload["user_id"])

    await manager.connect(conversation_id, websocket, user_id)

    try:
        while True:
            text = await websocket.receive_text()

            message = {
                "conversation_id": conversation_id,
                "sender_id": user_id,
                "content": text
            }

            await manager.broadcast(conversation_id, message)

    except WebSocketDisconnect:
        manager.disconnect(conversation_id, websocket)
        print(f"User {user_id} disconnected")