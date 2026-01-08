from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from typing import Dict, List, Tuple
from sqlalchemy.future import select
from fastapi.middleware.cors import CORSMiddleware

from app.auth import decode_jwt
from app.database import AsyncSessionLocal
from app.models import Message, Conversation
from app.services.conversation_access import validate_conversation_access

app = FastAPI()

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- CONNECTION MANAGER ----------------
class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, List[Tuple[WebSocket, int]]] = {}

    async def connect(self, room_id: str, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.rooms.setdefault(room_id, []).append((websocket, user_id))
        print(f"User {user_id} joined room {room_id}")

    def disconnect(self, room_id: str, websocket: WebSocket):
        if room_id not in self.rooms:
            return

        self.rooms[room_id] = [
            (ws, uid) for ws, uid in self.rooms[room_id] if ws != websocket
        ]

        if not self.rooms[room_id]:
            del self.rooms[room_id]

    async def broadcast(self, room_id: str, message: dict):
        for ws, _ in self.rooms.get(room_id, []):
            await ws.send_json(message)

manager = ConnectionManager()

# ---------------- SAVE MESSAGE ----------------
async def save_message(conversation_id: int, sender_id: int, content: str):
    async with AsyncSessionLocal() as session:
        msg = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content
        )
        session.add(msg)
        await session.commit()
        print("✅ Message saved")

# ---------------- ROOT ----------------
@app.get("/")
def root():
    return {"message": "FastAPI chat running"}

# ---------------- WEBSOCKET CHAT ----------------
@app.websocket("/ws/chat/{conversation_id}")
async def websocket_chat(
    websocket: WebSocket,
    conversation_id: int,
    token: str = Query(...)
):
    payload = decode_jwt(token)

    if not payload or "user_id" not in payload:
        await websocket.close(code=1008)
        return

    user_id = int(payload["user_id"])
    room_id = str(conversation_id)

    print(f"User {user_id} connecting to conversation {conversation_id}")

    # 🔐 Ownership validation
    is_allowed = await validate_conversation_access(
        conversation_id=conversation_id,
        user_id=user_id
    )
    print(f"Access allowed: {is_allowed}")
    print(f"Validating access for user {user_id} to conversation {conversation_id}")


    if not is_allowed:
        print("❌ Unauthorized access")
        await websocket.close(code=1008)
        return

    await manager.connect(room_id, websocket, user_id)

    try:
        while True:
            text = await websocket.receive_text()

            await save_message(
                conversation_id=conversation_id,
                sender_id=user_id,
                content=text
            )

            await manager.broadcast(room_id, {
                "conversation_id": conversation_id,
                "sender_id": user_id,
                "content": text
            })

    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
        print(f"User {user_id} disconnected")

# ---------------- MESSAGE HISTORY ----------------
@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

    return [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "content": m.content,
            "created_at": m.created_at,
        }
        for m in messages
    ]
