"""Temps real: gestor de connexions WebSocket per a esdeveniments del TPV.

Permet emetre esdeveniments (comanda creada, pagada, taula ocupada, tancament...)
a tots els clients connectats (PDAs de cambrers, pantalla de cuina KDS).
"""
import asyncio
import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Registra connexions WebSocket i hi emet missatges JSON."""

    def __init__(self):
        self.active: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, event: str, payload: Any):
        """Envia {event, payload} a tots els clients connectats."""
        message = json.dumps({"event": event, "payload": payload}, default=str)
        dead: list[WebSocket] = []
        for ws in list(self.active):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()

_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop):
    """Guarda l'event loop principal de FastAPI (es crida al lifespan)."""
    global _main_loop
    _main_loop = loop


async def emit(event: str, payload: Any):
    """Conveniència: emetre un esdeveniment sense preocupar-se pel manager."""
    await manager.broadcast(event, payload)


def emit_sync(event: str, payload: Any):
    """Emet un esdeveniment DES d'un handler síncron (threadpool).

    Programa el broadcast a l'event loop principal. Si no hi ha loop (p. ex.
    en un test sense servidor), no fa res (best effort).
    """
    if _main_loop is None or _main_loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(manager.broadcast(event, payload), _main_loop)
    except Exception:
        pass
