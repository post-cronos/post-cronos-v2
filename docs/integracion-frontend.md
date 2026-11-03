# Integración Frontend ↔ Infraestructura (v2)

Guía para la persona que desarrolla el frontend. No requiere acceso a Google Cloud ni credenciales: todo se conecta por HTTPS contra la API.

---

## 1. Idea general

La web es **estática** (GitHub Pages o dominio propio) y consume una **API en Cloud Run**. Las imágenes se suben a un bucket privado mediante una **URL firmada**; el procesamiento con IA ocurre en el servidor.

```
Frontend  ──►  API (Cloud Run)  ──►  URL firmada
   │                                   │
   └── PUT del JPG ───────────────────► GCS
                                        │
                                        ▼
                                   Processor + Gemini
                                        │
                                        ▼
                                    BigQuery
   ◄── GET /api/data ───────────────────┘
```

**Regla de oro:** el frontend nunca ve ni usa una service account, un JSON de credenciales ni una key de Google.

---

## 2. Configuración de la API

Definir la URL base antes de cargar el script principal:

```html
<script>
  window.POST_CRONOS_API = "https://post-cronos-api-XXXXX-uc.a.run.app";
</script>
```

- Sin barra final.
- Debe ser HTTPS (excepto `localhost` en desarrollo).
- En desarrollo también se puede pasar por query string:

```
http://localhost:8765/index.html?api=http://localhost:8080
```

El código actual ya soporta `window.POST_CRONOS_API` y `?api=`.

---

## 3. CORS

La API solo acepta los orígenes configurados en `ALLOWED_ORIGINS`. Para el frontend hay que pedir que agreguen el origen exacto, por ejemplo:

```
https://<dominio>
https://www.<dominio>
https://post-cronos.github.io
http://localhost:8765
```

- Incluye esquema, host y puerto si corresponde.
- En producción no usar `*`.
- La API responde a `OPTIONS` (preflight).

---

## 4. Contrato de datos

`GET /api/data` devuelve un array de participantes:

```json
[
  {
    "id": "santa_ana_5334",
    "edad": 11,
    "genero": "Femenino",
    "ciudad_barrio": "Villa Belgrano",
    "colegio": "Instituto Santa Ana",
    "eje": "Moda, Tecnologia",
    "img": "https://.../api/img/uploads/santa_ana/20261102_ab12.jpg",
    "interp": "El dibujo muestra...",
    "diseno": "Texto literal escrito por el participante"
  }
]
```

Notas:

- `id` es único.
- `edad` puede ser `null`.
- `genero` es uno de: `Masculino`, `Femenino`, `No binario`, `Otro`, `No responder`, o `null`.
- `eje` puede tener **varios valores separados por coma** (`"Moda, Tecnologia"`). Para filtros, separar por coma y hacer `trim`.
- `img` puede ser una URL de proxy (`/api/img/...`) o una URL firmada. No modificarla ni agregar parámetros.
- `interp` y `diseno` pueden ser `null`.

---

## 5. Endpoints

### `GET /health`

Para verificar que la API está viva.

```json
{ "ok": true, "project": "...", "bucket": "..." }
```

### `GET /api/data`

Devuelve el array del punto 4. Usar cache `no-store` o refrescar después de una subida.

### `GET /api/img/{objectName}`

Sirve una imagen del bucket privado. Se usa como `src` de `<img>`. No requiere headers.

### `POST /api/upload-url`

Pide una URL firmada para subir el JPG.

Request:

```json
{
  "filename": "IMG_5334.JPG",
  "contentType": "image/jpeg",
  "size": 1234567,
  "school": "santa_ana"
}
```

Response `200`:

```json
{
  "uploadUrl": "https://storage.googleapis.com/...",
  "objectName": "uploads/santa_ana/20261102_ab12cd34.jpg",
  "expiresAt": "2026-11-02T22:45:00Z"
}
```

Reglas:

- `contentType` debe ser `image/jpeg`.
- `size` máximo: 10 MB (`MAX_UPLOAD_MB`).
- `school` es opcional; se usa para organizar carpetas.
- La URL vence en pocos minutos y es de un solo uso.

### `PUT {uploadUrl}`

Subir el archivo.

Headers:

```
Content-Type: image/jpeg
```

Body: el archivo binario. No agregar headers de autenticación.

### `GET /api/status?object={objectName}`

Consultar el estado del procesamiento. `objectName` va URL-encoded.

```json
{ "status": "processing", "record": null }
```

Estados: `pending`, `processing`, `done`, `error`.

Cuando `status` es `done`, `record` trae el participante ya insertado (mismo formato que `/api/data`).

### `POST /api/upload` (alternativa multipart)

Si no se usa URL firmada, se puede subir el archivo a la API:

```
Content-Type: multipart/form-data
file: <JPG>
school: <texto opcional>
```

Responde `202` con `{ "objectName": "..." }`. El procesamiento también ocurre por evento.

### Errores

| Código | Significado |
|---|---|
| `400` | Tipo inválido, archivo vacío o JPG inválido |
| `413` | Supera el tamaño máximo |
| `429` | Demasiadas subidas desde esa IP |
| `502` | Falló Gemini o BigQuery |
| `503` | Servidor ocupado; reintentar |

El cuerpo de error tiene `{ "detail": "mensaje" }`.

---

## 6. Flujo recomendado de subida

1. Validar en el cliente: JPG/JPEG y ≤ 10 MB (solo UX; el servidor valida igual).
2. Pedir `POST /api/upload-url`.
3. Subir con `PUT` a `uploadUrl`, mostrando progreso.
4. Consultar `GET /api/status` cada 2 segundos hasta `done` o `error`.
5. Refrescar `/api/data` o usar el `record` devuelto.
6. Mostrar el dibujo en la galería.

### Ejemplo de subida

```js
async function subirJpg(file, school, onProgress) {
  if (!/^image\/jpe?g$/i.test(file.type)) throw new Error("Solo se aceptan JPG");
  if (file.size > 10 * 1024 * 1024) throw new Error("Máximo 10 MB");

  const api = window.POST_CRONOS_API.replace(/\/$/, "");

  const res = await fetch(api + "/api/upload-url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      filename: file.name,
      contentType: "image/jpeg",
      size: file.size,
      school
    })
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "No se pudo preparar la subida");
  }

  const { uploadUrl, objectName } = await res.json();

  await new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", "image/jpeg");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new Error("Error al subir el archivo"));
    };
    xhr.onerror = () => reject(new Error("Error de red"));
    xhr.send(file);
  });

  return objectName;
}
```

### Ejemplo de espera

```js
async function esperarProcesado(objectName, { intentos = 30, ms = 2000 } = {}) {
  const api = window.POST_CRONOS_API.replace(/\/$/, "");
  const url = api + "/api/status?object=" + encodeURIComponent(objectName);

  for (let i = 0; i < intentos; i++) {
    const res = await fetch(url, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      if (data.status === "done") return data.record;
      if (data.status === "error") throw new Error("No se pudo procesar el dibujo");
    }
    await new Promise((r) => setTimeout(r, ms));
  }
  throw new Error("El procesamiento está demorando más de lo esperado");
}
```

---

## 7. Estados de UI sugeridos

- **Sin archivo:** botón deshabilitado.
- **Archivo elegido:** vista previa + datos del archivo.
- **Subiendo:** barra de progreso 0–100 %.
- **Procesando:** spinner + “La IA está leyendo el formulario…”.
- **Listo:** mensaje y enlace a la galería.
- **Error:** mensaje claro y botón para reintentar.

La subida directa a GCS termina antes que el procesamiento; no hace falta mantener la pestaña abierta para que el servidor termine.

---

## 8. Seguridad

- No poner keys, tokens de Google ni `gs://` en el frontend.
- No llamar a la API de GCS con credenciales; solo usar la URL firmada.
- No confiar en la validación del cliente: el servidor valida tipo y tamaño.
- Respetar el rate limit (5 subidas cada 10 minutos por IP). Mostrar un mensaje amable en `429`.
- Si en el futuro se agrega captcha o clave, coordinarlo con el backend.

---

## 9. Desarrollo local

1. Servir la web:

```bash
python -m http.server 8765
```

2. Abrir:

```
http://localhost:8765/index.html?api=http://localhost:8080
```

3. Verificar la API:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/api/data
```

4. Si el backend no está corriendo, la web usa `data.js` como respaldo y el formulario de subida muestra que falta configuración.

---

## 10. Dominio propio

- El frontend puede vivir en `https://<dominio>` con GitHub Pages o Cloudflare Pages.
- La API puede seguir en la URL de Cloud Run (`https://...run.app`).
- Si el origen del frontend cambia, hay que actualizar `ALLOWED_ORIGINS` en el backend.
- Si se usa `api.<dominio>`, coordinar con infraestructura; no es obligatorio para la primera versión.

---

## 11. Cambios de contrato

- Cualquier cambio de campos, endpoints o códigos de error se documenta acá y se avisa al frontend.
- Si un cambio rompe compatibilidad, crear `/api/v2` y mantener `/api` mientras se migra.

---

## 12. Checklist de integración

- [ ] `window.POST_CRONOS_API` configurado.
- [ ] Origen del frontend agregado a `ALLOWED_ORIGINS`.
- [ ] `/api/data` carga la galería y el dashboard.
- [ ] Las imágenes (`img`) se ven.
- [ ] `POST /api/upload-url` devuelve URL firmada.
- [ ] El `PUT` a GCS sube el JPG con progreso.
- [ ] `/api/status` pasa de `processing` a `done`.
- [ ] El registro nuevo aparece en `/api/data`.
- [ ] Errores 400/413/429/502/503 muestran mensajes claros.
- [ ] Funciona en mobile y en el dominio propio con HTTPS.
