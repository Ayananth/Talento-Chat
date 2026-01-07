from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from typing import Dict, List, Tuple
from sqlalchemy.future import select

from app.auth import decode_jwt
from app.database import AsyncSessionLocal
from app.models import Message
from app.models import Conversation

app = FastAPI()




async def ensure_conversation(conversation_id: int, session):
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    if not result.scalar():
        session.add(
            Conversation(
                id=conversation_id,
                job_id=0,
                jobseeker_id=0,
                recruiter_id=0
            )
        )
        await session.commit()

# ---------------- SAVE MESSAGE ----------------
async def save_message(conversation_id: int, sender_id: int, content: str):
    try:
        async with AsyncSessionLocal() as session:
            msg = Message(
                conversation_id=conversation_id,
                sender_id=sender_id,
                content=content
            )
            await ensure_conversation(conversation_id, session)

            session.add(msg)
            await session.commit()
            print("✅ Message saved to DB")
    except Exception as e:
        print("❌ DB save failed:", e)


# ---------------- CONNECTION MANAGER ----------------
class ConnectionManager:
    def __init__(self):
        # room_id -> list of (websocket, user_id)
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

# ---------------- ROOT ----------------
@app.get("/")
def root():
    return {"message": "FastAPI is running"}


# ---------------- WEBSOCKET CHAT ----------------
@app.websocket("/ws/chat/{conversation_id}")
async def websocket_chat(
    websocket: WebSocket,
    conversation_id: str,
    token: str = Query(...)
):
    payload = decode_jwt(token)

    if not payload or "user_id" not in payload:
        await websocket.close(code=1008)
        return

    user_id = int(payload["user_id"])

    await manager.connect(conversation_id, websocket, user_id)

    try:
        while True:
            text = await websocket.receive_text()

            await save_message(
                conversation_id=int(conversation_id),
                sender_id=user_id,
                content=text
            )

            await manager.broadcast(conversation_id, {
                "conversation_id": conversation_id,
                "sender_id": user_id,
                "content": text
            })

    except WebSocketDisconnect:
        manager.disconnect(conversation_id, websocket)
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
            "created_at": m.created_at
        }
        for m in messages
    ]
