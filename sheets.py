"""
Lectura del catálogo de productos desde Google Sheets.

Autenticación con `google.auth.default()`:
  - En local  → toma la cuenta de servicio vía GOOGLE_APPLICATION_CREDENTIALS (llave JSON).
  - En Cloud Run → toma la cuenta de servicio adjunta (sin llave).
El mismo código corre en ambos entornos.
"""

import os
import google.auth
from googleapiclient.discovery import build

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "14yF2rXVaXRG2KKQQNCogHzXck2s3IXPWbx2xeAc9B6Y")
SHEET_RANGE = os.getenv("GOOGLE_SHEET_RANGE", "A:H")
GCS_BUCKET = os.getenv("GCS_BUCKET", "troko-content")

_service = None


def _get_service():
    """Crea (una vez) el cliente de la API de Sheets."""
    global _service
    if _service is None:
        creds, _ = google.auth.default(scopes=_SCOPES)
        _service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return _service


def _to_int(value, default=0):
    try:
        return int(str(value).strip())
    except (ValueError, AttributeError):
        return default


def _redondear_990(monto):
    """
    Deja los últimos 3 dígitos en 990 dentro del mismo millar.
    Ej: 23543 → 23990, 23995 → 23990, 750 → 990.
    """
    return (monto // 1000) * 1000 + 990


def _normalize_carpeta(imagen_url):
    """
    La hoja guarda 'troko-content/imagenes-pagina-web/<producto>'.
    El frontend lista imágenes con un prefijo relativo al bucket, así que
    le quitamos el nombre del bucket y los slashes sobrantes.
    """
    path = (imagen_url or "").strip().strip("/")
    bucket_prefix = f"{GCS_BUCKET}/"
    if path.startswith(bucket_prefix):
        path = path[len(bucket_prefix):]
    return path


def fetch_products():
    """Devuelve la lista de productos como dicts tipados, leídos de la Sheet."""
    service = _get_service()
    resp = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SHEET_ID, range=SHEET_RANGE)
        .execute()
    )
    rows = resp.get("values", [])
    if not rows:
        return []

    headers = [h.strip() for h in rows[0]]
    products = []
    for row in rows[1:]:
        if not row or not row[0].strip():  # salta filas sin id
            continue
        # rellena columnas faltantes para que el zip no se corte
        padded = row + [""] * (len(headers) - len(row))
        data = dict(zip(headers, padded))
        precio = _to_int(data.get("precio"))
        descuento = _to_int(data.get("descuento"))
        stock = _to_int(data.get("stock"))
        products.append(
            {
                "id": data.get("id", "").strip(),
                "nombre": data.get("nombre", "").strip(),
                "precio": precio,
                "descuento": descuento,
                # Precio final calculado en el servidor (regla de negocio): el
                # frontend nunca debe recalcular precio/stock por seguridad.
                # Se aplica el descuento y luego se redondea a X990.
                "precioFinal": _redondear_990(
                    precio - round(precio * descuento / 100)
                ),
                "descripcion": data.get("descripcion", "").strip(),
                "categoria": data.get("categoria", "").strip(),
                "stock": stock,
                "agotado": stock <= 0,
                "carpeta": _normalize_carpeta(data.get("imagenUrl")),
            }
        )
    return products
