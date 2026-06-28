# Troko API — Backend

API en **FastAPI** que lee el catálogo desde **Google Sheets** (fuente de verdad de
precio/descuento/stock) y lo expone como JSON para el frontend. Despliegue en **Cloud Run**.

## Endpoints

| Método | Ruta               | Descripción                              |
| :----- | :----------------- | :--------------------------------------- |
| GET    | `/health`          | Sonda de salud.                          |
| GET    | `/products`        | Lista de productos.                      |
| GET    | `/products/{id}`   | Un producto (404 si no existe).          |

Cada producto incluye `precioFinal` y `agotado` **calculados en el servidor**
(el frontend nunca recalcula precio/stock por seguridad).

## Variables de entorno

| Variable             | Default                         | Para qué                                    |
| :------------------- | :------------------------------ | :------------------------------------------ |
| `GOOGLE_SHEET_ID`    | (id de la Sheet en el código)   | Hoja a leer.                                |
| `GOOGLE_SHEET_RANGE` | `A:H`                           | Rango de columnas.                          |
| `GCS_BUCKET`         | `troko-content`                 | Bucket para normalizar la `carpeta`.        |
| `ALLOWED_ORIGINS`    | `localhost:5173,localhost:4173` | Orígenes CORS (coma-separado). En prod: dominio de Firebase. |
| `CACHE_TTL`          | `60`                            | Segundos de caché en memoria de `/products`.|

## Autenticación (ADC)

`google.auth.default()` resuelve credenciales automáticamente:
- **Local:** apunta `GOOGLE_APPLICATION_CREDENTIALS` a la llave JSON de la cuenta de servicio.
- **Cloud Run:** usa la **cuenta de servicio adjunta** (`troko-mkt-agent@mapapp-405311.iam.gserviceaccount.com`), sin archivo de llave.

> ⚠️ La Sheet debe estar **compartida como Lector** con `troko-mkt-agent@mapapp-405311.iam.gserviceaccount.com`.
> La llave `troko-sa-key.json` **no se commitea** ni entra a la imagen (ver `.gitignore` / `.dockerignore`).

## Correr en local

```bash
cd PaginaWeb/backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/troko-sa-key.json"
uvicorn main:app --reload --port 8080

# probar
curl http://localhost:8080/health
curl http://localhost:8080/products
```

## Deploy a Cloud Run

Proyecto `mapapp-405311`, cuenta de servicio `troko-mkt-agent`. Desde `PaginaWeb/backend/`:

```bash
gcloud config set project mapapp-405311

gcloud run deploy troko-api \
  --source . \
  --region southamerica-west1 \
  --service-account troko-mkt-agent@mapapp-405311.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --min-instances 0 \
  --set-env-vars "ALLOWED_ORIGINS=https://TU-PROYECTO.web.app,https://TU-PROYECTO.firebaseapp.com"
```

Notas:
- `--source .` deja que Cloud Build use el `Dockerfile` de esta carpeta.
- `--allow-unauthenticated`: el catálogo es público; se restringe por **CORS** con `ALLOWED_ORIGINS`.
- `--min-instances 1` reduce el *cold start* (tiene costo); déjalo en `0` mientras desarrollas.
- Tras desplegar, copia la URL del servicio (`https://troko-api-XXXX.run.app`) en
  `PaginaWeb/project/.env.local` → `VITE_API_URL`, y rebuild del frontend.
```
