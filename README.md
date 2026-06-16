# finanzas-aftt-api

API backend para el planner de gastos construida con FastAPI, MongoDB y sesiones bearer token.

## Tecnologias

- Python 3.11
- FastAPI
- Uvicorn
- MongoDB
- Motor

## Que hace la API

La API cubre tres bloques principales:

- Autenticacion por `username` y password.
- Cambio obligatorio de contrasena en el primer acceso para usuarios con estado `New`, con cambio opcional de `username`.
- Gestion del planner financiero por usuario autenticado:
  - listado de anos disponibles,
  - detalle mensual,
  - ingresos por quincena,
  - alta y edicion de gastos,
  - marcar gastos como pagados o pendientes,
  - cierre de mes.

Cuando un usuario entra por primera vez en el planner, el backend genera automaticamente la estructura base de datos para el ano actual y el siguiente, con 12 meses y 2 quincenas por mes.

## Requisitos

- Python 3.11 o superior
- MongoDB accesible desde `MONGO_URI`
- La conexion actual del backend fuerza TLS, por lo que el servidor Mongo configurado debe aceptar conexiones TLS

## Variables de entorno

El proyecto usa un archivo `.env`.

1. Copia el ejemplo:

```bash
cp .env.example .env
```

2. Ajusta los valores necesarios.

Variables disponibles:

- `APP_NAME`: nombre de la app.
- `APP_ENV`: entorno, por ejemplo `development`.
- `APP_DEBUG`: `true` o `false`.
- `APP_HOST`: host de arranque.
- `APP_PORT`: puerto de arranque.
- `MONGO_URI`: cadena de conexion de MongoDB.
- `MONGO_DB_NAME`: nombre de la base de datos.
- `SESSION_SECRET_KEY`: clave usada para hashear el token de sesion.
- `SESSION_EXPIRE_DAYS`: duracion de la sesion en dias.
- `CORS_ORIGINS`: array JSON con los origenes permitidos.

Ejemplo:

```env
CORS_ORIGINS=["http://localhost:5173", "https://tu-frontend.com"]
```

Si vas a usar MongoDB local, revisa que acepte TLS. La implementacion actual crea el cliente con `tls=True`.

## Generar claves

### 1. Generar `SESSION_SECRET_KEY`

Debe tener al menos 16 caracteres.

Opcion con OpenSSL:

```bash
openssl rand -hex 32
```

Opcion con Python:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Pega el valor generado en `.env`:

```env
SESSION_SECRET_KEY=pega_aqui_tu_valor
```

### 2. Generar hash de contrasena para usuarios

La API no crea usuarios por endpoint. Para cargar usuarios manualmente en MongoDB, primero genera el `passwordHash`:

```bash
python3 -m app.scripts.hash_password Temp12345
```

El comando devuelve un hash en formato `pbkdf2_sha256$...` listo para guardar en la coleccion `users`.

## Crear usuarios manualmente

Coleccion: `users`

Usuario nuevo, obligado a cambiar contrasena en el primer login:

```json
{
  "username": "new.user",
  "passwordHash": "pbkdf2_sha256$...",
  "status": "New"
}
```

Usuario activo:

```json
{
  "username": "active.user",
  "passwordHash": "pbkdf2_sha256$...",
  "status": "Active"
}
```

Notas:

- El username debe guardarse en minusculas.
- Los estados validos son `New` y `Active`.
- Si el documento no tiene `id`, el backend puede normalizarlo usando el valor de `_id`.
- Un usuario `New` no puede usar el planner hasta cambiar su contrasena inicial.

## Levantar el proyecto en local

1. Crear entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Configurar `.env`.

4. Arrancar la API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Endpoints utiles una vez levantada:

- `http://localhost:8000/`
- `http://localhost:8000/health`
- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Uso del token

El login devuelve un `accessToken`. Las rutas privadas esperan este header:

```http
Authorization: Bearer <accessToken>
```

## Levantar con Docker

Construir la imagen:

```bash
docker build -t finanzas-aftt-api .
```

Ejecutar el contenedor:

```bash
docker run --rm -p 8000:8000 --env-file .env finanzas-aftt-api
```

## Flujo de autenticacion

1. `POST /auth/login`
2. La API devuelve `accessToken` y el usuario autenticado.
3. `GET /auth/me` devuelve el usuario autenticado usando `Authorization: Bearer ...`.
4. Si el usuario tiene estado `New`, debe llamar a `POST /auth/change-initial-password` con el token actual.
5. Cuando el usuario queda en estado `Active`, ya puede usar los endpoints de `/planner`.
6. `POST /auth/logout` elimina la sesion actual.

## Endpoints principales

### Root

- `GET /`
- `GET /health`

### Auth

- `GET /auth/me`
- `POST /auth/login`
- `POST /auth/change-initial-password`
- `POST /auth/logout`

### Planner

- `GET /planner/years`
- `GET /planner/years/{year}`
- `GET /planner/years/{year}/months/{month}`
- `PATCH /planner/fortnights/{fortnight_id}/income`
- `POST /planner/expenses`
- `PATCH /planner/expenses/{expense_id}/status`
- `PUT /planner/expenses/{expense_id}`
- `PATCH /planner/months/{month_id}/close`

## Reglas funcionales importantes

- Los endpoints del planner solo aceptan usuarios autenticados con estado `Active`.
- Los meses cerrados no permiten cambios de ingresos ni de gastos.
- Un gasto debe pertenecer al mismo mes y a la misma quincena indicada en la peticion.
- El cierre de mes requiere confirmacion explicita con `confirmClose=true`.
- Las sesiones se guardan en MongoDB y expiran automaticamente por indice TTL.
- En el primer acceso, la contrasena nueva es obligatoria y el cambio de `username` es opcional.

## Notas tecnicas

- La aplicacion crea indices al arrancar para `users`, `sessions` y `month_periods`.
- La conexion Mongo se inicializa al levantar la app.
- La documentacion OpenAPI esta disponible en `/docs` y `/redoc`.

## Documentacion relacionada

- `MANUAL_USERS.md`: referencia rapida para alta manual de usuarios.
