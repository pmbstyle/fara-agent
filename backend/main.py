from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import logging
import base64
import io
import sys
import os
from PIL import Image

# Add parent directory to path to import agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import FaraAgent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "start_task":
                task = message.get("task")
                if task:
                    # Run agent in background
                    asyncio.create_task(run_agent_task(task))
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def run_agent_task(task: str):
    logger = logging.getLogger("fara_agent_web")
    logger.setLevel(logging.INFO)

    # Load default config
    try:
        with open("config.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {}

    async def on_update(data):
        # Transform data for frontend if needed
        msg = data.copy()
        if msg["type"] == "screenshot":
            # Convert PIL Image to base64
            img = msg["image"]

            # Resize if too large for web view
            max_width = 1024
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=70) # Use JPEG with compression
            img_str = base64.b64encode(buffered.getvalue()).decode()
            msg["image"] = f"data:image/jpeg;base64,{img_str}"

        await manager.broadcast(msg)

    agent = FaraAgent(
        config=config,
        headless=True, # Web agent should probably be headless by default
        logger=logger,
        on_update=on_update
    )

    try:
        await manager.broadcast({"type": "status", "content": "Agent starting..."})
        await agent.start()
        await agent.run(task)
        await manager.broadcast({"type": "status", "content": "Agent finished."})
    except Exception as e:
        await manager.broadcast({"type": "error", "content": str(e)})
    finally:
        await agent.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
