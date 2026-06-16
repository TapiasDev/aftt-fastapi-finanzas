# Manual User Setup

## Generar hash de contraseña

```bash
python3 -m app.scripts.hash_password Temp12345
```

El comando devuelve un valor `passwordHash` listo para guardar en MongoDB.

## Documento mínimo para usuario nuevo

Colección: `users`

```json
{
  "email": "new.user@example.com",
  "passwordHash": "pbkdf2_sha256$...",
  "status": "New"
}
```

## Documento mínimo para usuario activo

Colección: `users`

```json
{
  "email": "active.user@example.com",
  "passwordHash": "pbkdf2_sha256$...",
  "status": "Active"
}
```

## Notas

- El backend puede completar el campo `id` automáticamente en el primer login si el documento solo tiene `_id`.
- El email debe quedar en minúsculas.
- Los únicos estados válidos son `New` y `Active`.
- En el primer acceso de un usuario `New`, la API obligará el cambio de contraseña antes de entrar al planner.
