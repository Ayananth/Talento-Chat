from fastapi import FastAPI, WebSocket

app = FastAPI()


@app.get("/")
def root():
    return {"message": "FastAPI is running"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    while True:
        data = await websocket.receive_text()
        print("Received:", data)
        await websocket.send_text(f"Echo: {data} from server")
