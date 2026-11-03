# Resumen del estado del proyecto — Post-Cronos

Última actualización: 2026-11-02

---

## 1. Cuentas y repositorios

| Qué | Dónde |
|---|---|
| Cuenta GitHub nueva | `post-cronos` (`info.postcronos@gmail.com`) |
| Repo v1 (estable) | https://github.com/post-cronos/post-cronos |
| Sitio v1 | https://post-cronos.github.io/post-cronos/ |
| Repo v2 (documentación + código en desarrollo) | https://github.com/post-cronos/post-cronos-v2 |
| Cuenta Google nueva | `info.postcronos@gmail.com` |
| Cuenta/repo anterior | `Learmonelli/post-cronos`, `leandroarmonelli@gmail.com` |

En la copia local de la v1, el remoto viejo quedó guardado como `old-origin`.

---

## 2. Qué se hizo

### GitHub

- Se creó la cuenta `post-cronos` y el repo `post-cronos/post-cronos`.
- Se migró el historial (5 commits originales) y se agregaron:
  - `e0c3efd`: scripts de procesamiento, OCR y documentación técnica.
  - `49df416`: actualización de URLs y repo al nuevo GitHub.
  - `9b105b2`: subida de dibujos JPG con backend Cloud Run.
- Se activó GitHub Pages en `https://post-cronos.github.io/post-cronos/`.
- Se creó el repo `post-cronos/post-cronos-v2` con:
  - Plan de infraestructura v2 (`README.md`).
  - Copia de la web, backend y scripts legacy.
  - Guías de integración para frontend.

### Documentación

- `README.md`: arquitectura v2, Eventarc, migración, dominio propio, costos, seguridad.
- `docs/integracion-frontend.md`: contrato técnico completo para frontend.
- `docs/instructivo-frontend-simple.md`: guía paso a paso para alguien sin experiencia.
- `docs/ejemplo-subida.html`: ejemplo mínimo funcional.
- `docs/post-cronos-infraestructura.md`: documento técnico de la v1.

---

## 3. Estado actual del código

### v1 (`post-cronos/post-cronos`)

- Web estática en GitHub Pages.
- Backend en Cloud Run (`backend/main.py`) con procesamiento **síncrono**:
  - sube a GCS,
  - llama a Gemini,
  - inserta en BigQuery,
  - todo en el mismo request.
- El botón de subida está publicado pero **deshabilitado** hasta configurar `window.POST_CRONOS_API`.
- Bucket público, scripts con proyecto y key hardcodeados.

### v2 (`post-cronos/post-cronos-v2`)

- Solo se copió el código base de la v1; **todavía no está refactorizado**.
- Falta implementar:
  - `backend/api/` con `/api/data`, `/api/img`, `/api/upload-url`, `/api/status`.
  - `backend/processor/` que consume eventos de GCS (Eventarc).
  - `backend/common.py` con configuración, prompt, idempotencia y acceso a GCP.
  - Trigger de Eventarc.
  - Bucket privado y proxy de imágenes.

---

## 4. Arquitectura objetivo v2

```
Web
  │ POST /api/upload-url
  ▼
Cloud Run API ──► URL firmada
  │ PUT directo
  ▼
GCS privado
  │ object.finalized
  ▼
Eventarc ──► Cloud Run Processor
  │ Gemini
  ▼
BigQuery ──► GET /api/data ──► galería
```

Beneficios:

- Procesa tanto subidas web como subidas directas al bucket.
- No pierde imágenes si Gemini falla (reintentos).
- No duplica filas (idempotencia).
- No expone imágenes de menores (bucket privado).

---

## 5. Decisiones tomadas

- La v2 se desarrolla en `post-cronos/post-cronos-v2`; la v1 queda congelada.
- Procesamiento recomendado: **Eventarc en tiempo real**.
- Alternativa si el costo es crítico: **lote con Cloud Scheduler** cada 15/60 min.
- Bucket **privado**; imágenes por proxy o URL firmada.
- Sin keys JSON en el repo; Cloud Run usa service account adjunta.
- El frontend solo necesita la URL de la API, nunca credenciales de Google.
- Dominio propio: queda documentado para la v2; falta el dominio exacto y el registrador.

---

## 6. Pendientes

### Infraestructura / Google Cloud

- [ ] Obtener permisos de la cuenta de facturación (`roles/billing.user`) y Owner/Editor del proyecto.
- [ ] Confirmar el **Project ID** del proyecto nuevo.
- [ ] Crear/vincular proyecto y habilitar APIs.
- [ ] Crear service accounts y roles mínimos.
- [ ] Crear bucket privado y dataset/tabla.
- [ ] Migrar imágenes de GCS y filas de BigQuery.
- [ ] Implementar y deployar API + Processor + Eventarc.
- [ ] Configurar presupuesto y alertas.
- [ ] Revocar la key vieja y el acceso de la cuenta personal.

### Código v2

- [ ] Refactorizar el backend en `api` + `processor` + `common`.
- [ ] Implementar URLs firmadas y polling de estado.
- [ ] Idempotencia con tabla `procesados`.
- [ ] Filtros de extensión/prefijo y validación de JPG.
- [ ] Probar subida web, subida directa y reprocesamiento.

### Frontend

- [ ] Pasarle al responsable el instructivo simple y la URL de la API.
- [ ] Configurar `window.POST_CRONOS_API`.
- [ ] Agregar el origen del frontend a `ALLOWED_ORIGINS`.
- [ ] Probar galería, subida, progreso y errores.

### Dominio

- [ ] Confirmar dominio y registrador.
- [ ] Agregar `CNAME` y registros DNS.
- [ ] Activar HTTPS.
- [ ] Actualizar `ALLOWED_ORIGINS` con el dominio final.

---

## 7. Enlaces útiles

- Plan v2: https://github.com/post-cronos/post-cronos-v2/blob/main/README.md
- Guía técnica frontend: https://github.com/post-cronos/post-cronos-v2/blob/main/docs/integracion-frontend.md
- Instructivo simple: https://github.com/post-cronos/post-cronos-v2/blob/main/docs/instructivo-frontend-simple.md
- Ejemplo de subida: https://github.com/post-cronos/post-cronos-v2/blob/main/docs/ejemplo-subida.html
- Repo v1: https://github.com/post-cronos/post-cronos
- Sitio v1: https://post-cronos.github.io/post-cronos/

---

## 8. Notas de seguridad

- La key de service account **no** está en ningún repo; sigue solo en la máquina local.
- No commitear archivos `*-service-account.json` ni `laboratorio-cordoba-*.json`.
- Antes de publicar la v2, revisar consentimientos de imagen de menores.
- Activar 2FA en GitHub, Google y el registrador del dominio.
