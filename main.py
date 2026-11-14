"""
API del catálogo de Troko (FastAPI sobre Cloud Run).

Lee los productos desde Google Sheets (fuente de verdad de precio/stock) vía
`sheets.fetch_products()` y los expone como JSON para el frontend.

Endpoints:
  GET /health          → sonda de salud (para Cloud Run / uptime checks)
  GET /products        → lista completa de productos
  GET /products/{id}   → un producto por id (404 si no existe)

La lista se cachea en memoria por `CACHE_TTL` segundos para no pegarle a la
Sheet en cada request (la API de Sheets tiene cuotas).
"""

import os
import time
import logging
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from sheets import fetch_products

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Orígenes permitidos para CORS. En prod se setea ALLOWED_ORIGINS con el dominio
# de Firebase Hosting (coma-separado). En dev valen los puertos de Vite.
_DEFAULT_ORIGINS = (
    "http://localhost:5173,http://localhost:5174,http://localhost:4173"
)
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if o.strip()
]

# Segundos que se cachea la lista de productos en memoria.
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))


# --- Modelo de respuesta (alimenta el esquema de Swagger) -----------------
class Product(BaseModel):
    id: str = Field(..., examples=["med_2b_001"])
    nombre: str = Field(..., examples=["Medallero Troko 2 Barras"])
    precio: int = Field(..., description="Precio base en CLP", examples=[24990])
    descuento: int = Field(..., description="Descuento en %", examples=[15])
    precioFinal: int = Field(..., description="Precio con descuento aplicado y redondeado a X990 (CLP)", examples=[21990])
    descripcion: str
    categoria: str = Field(..., examples=["Medalleros"])
    stock: int = Field(..., examples=[12])
    agotado: bool = Field(..., description="True si stock <= 0")
    carpeta: str = Field(
        ...,
        description="Prefijo de la carpeta en el bucket GCS; el frontend lista sus imágenes.",
        examples=["imagenes-pagina-web/medallero_2_barras"],
    )


app = FastAPI(
    title="Troko API",
    version="1.0.0",
    description=(
        "API del catálogo de Troko. Lee precio, descuento y stock desde Google "
        "Sheets (fuente de verdad) y los expone para el frontend. Las imágenes se "
        "sirven desde Google Cloud Storage."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# --- Caché TTL en memoria -------------------------------------------------
_cache = {"data": None, "ts": 0.0}


def _get_products():
    """Devuelve los productos, usando la caché si aún es válida."""
    now = time.monotonic()
    if _cache["data"] is None or (now - _cache["ts"]) > CACHE_TTL:
        logger.info("Cache miss → leyendo productos desde Google Sheets")
        _cache["data"] = fetch_products()
        _cache["ts"] = now
    return _cache["data"]


# --- Endpoints ------------------------------------------------------------
@app.get("/health", tags=["infra"], summary="Sonda de salud")
def health():
    """Comprobación rápida de que el servicio está vivo (para Cloud Run)."""
    return {"status": "ok"}


@app.get(
    "/products",
    response_model=List[Product],
    tags=["catálogo"],
    summary="Lista todos los productos",
)
def list_products():
    """Devuelve el catálogo completo leído desde Google Sheets (cacheado en memoria)."""
    try:
        return _get_products()
    except Exception as e:
        logger.exception("Error leyendo productos")
        raise HTTPException(status_code=502, detail=f"Error leyendo la Sheet: {e}")


@app.get(
    "/products/{product_id}",
    response_model=Product,
    tags=["catálogo"],
    summary="Obtiene un producto por id",
    responses={404: {"description": "Producto no encontrado"}},
)
def get_product(product_id: str):
    """Devuelve un único producto por su `id` (404 si no existe)."""
    try:
        products = _get_products()
    except Exception as e:
        logger.exception("Error leyendo productos")
        raise HTTPException(status_code=502, detail=f"Error leyendo la Sheet: {e}")

    product = next((p for p in products if p["id"] == product_id), None)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product
