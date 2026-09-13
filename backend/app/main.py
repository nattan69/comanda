from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .api.routes import tables, menu, reservations, orders, staff, fiscal, integrations, closure, shifts, centers, establishments
from .db import engine, Base
from .models import models  # Importar modelos para que SQLAlchemy los registre

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialización automática del esquema de la base de datos.
    # Fase 0: create_all (idempotente). Sin migraciones Alembic por ahora.
    Base.metadata.create_all(bind=engine)
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

# Inclusión de routers
app.include_router(tables.router, prefix="/api/v1/tables", tags=["Tables"])
app.include_router(menu.router, prefix="/api/v1/menu", tags=["Menu"])
app.include_router(reservations.router, prefix="/api/v1/reservations", tags=["Reservations"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["Orders"])
app.include_router(staff.router, prefix="/api/v1/staff", tags=["Staff"])
app.include_router(fiscal.router, prefix="/api/v1/fiscal", tags=["Fiscal"])
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["Integrations"])
app.include_router(closure.router, prefix="/api/v1/closure", tags=["Closure"])
app.include_router(shifts.router, prefix="/api/v1/shifts", tags=["Shifts"])
app.include_router(centers.router, prefix="/api/v1/centers", tags=["Centers"])
app.include_router(establishments.router, prefix="/api/v1/establishments", tags=["Establishments"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
