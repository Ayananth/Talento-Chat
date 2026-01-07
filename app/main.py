from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        self.rooms.setdefault(room_id, []).append(websocket)
        print(f"Room {room_id} connections: {len(self.rooms[room_id])}")

    def disconnect(self, room_id: str, websocket: WebSocket):
        self.rooms[room_id].remove(websocket)

        if not self.rooms[room_id]:
            del self.rooms[room_id]

        print(f"Room {room_id} connections: {len(self.rooms.get(room_id, []))}")

    async def broadcast(self, room_id: str, message: str):
        for websocket in self.rooms.get(room_id, []):
            await websocket.send_text(message)


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
    conversation_id: str
):
    await manager.connect(conversation_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(
                conversation_id,
                f"[{conversation_id}] {data}"
            )

    except WebSocketDisconnect:
        manager.disconnect(conversation_id, websocket)
