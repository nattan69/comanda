from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .api.routes import tables, menu, reservations, orders, staff, fiscal, integrations, closure, shifts, centers, establishments, room_credits
from .db import engine, Base
from .models import models  # Importar modelos para que SQLAlchemy los registre
from .deps import require_auth
from .realtime import manager, set_main_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialización automática del esquema de la base de datos.
    # Fase 0: create_all (idempotente). Sin migraciones Alembic por ahora.
    Base.metadata.create_all(bind=engine)
    import asyncio
    set_main_loop(asyncio.get_running_loop())
    yield

app = FastAPI(title="Comanda Backend", version="0.1.0", lifespan=lifespan)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción restringir a dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


# Temps real (WebSocket): PDA de cambrers + pantalla de cuina (KDS)
@app.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Els clients només reben broadcasts; aquest receive manté la connexió viva.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Inclusión de routers (autenticación de dispositivo obligatoria en todos,
# salvo staff/login+logout e integraciones, que usan PIN y API key respectivamente)
app.include_router(tables.router, prefix="/api/v1/tables", tags=["Tables"], dependencies=[Depends(require_auth)])
app.include_router(menu.router, prefix="/api/v1/menu", tags=["Menu"], dependencies=[Depends(require_auth)])
app.include_router(reservations.router, prefix="/api/v1/reservations", tags=["Reservations"], dependencies=[Depends(require_auth)])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["Orders"], dependencies=[Depends(require_auth)])
app.include_router(staff.router, prefix="/api/v1/staff", tags=["Staff"])
app.include_router(fiscal.router, prefix="/api/v1/fiscal", tags=["Fiscal"], dependencies=[Depends(require_auth)])
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["Integrations"])
app.include_router(closure.router, prefix="/api/v1/closure", tags=["Closure"], dependencies=[Depends(require_auth)])
app.include_router(shifts.router, prefix="/api/v1/shifts", tags=["Shifts"], dependencies=[Depends(require_auth)])
app.include_router(centers.router, prefix="/api/v1/centers", tags=["Centers"], dependencies=[Depends(require_auth)])
app.include_router(establishments.router, prefix="/api/v1/establishments", tags=["Establishments"], dependencies=[Depends(require_auth)])
app.include_router(room_credits.router, prefix="/api/v1/room-credits", tags=["RoomCredits"], dependencies=[Depends(require_auth)])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
