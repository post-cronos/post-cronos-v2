# Post-Cronos v2 — Plan de infraestructura y dominio propio

Documento de planificación para la versión 2 del proyecto **Post-Cronos: Córdoba 2060**.

- Proyecto actual (v1): https://github.com/post-cronos/post-cronos
- Sitio actual: https://post-cronos.github.io/post-cronos/
- Este repositorio: documentación de la v2, sin código de producción.

---

## 1. Objetivo de la v2

Pasar de un prototipo operado manualmente a una infraestructura del proyecto:

1. Procesar automáticamente **cualquier imagen que llegue al bucket**, ya sea desde la web o subida a mano.
2. Separar la carga de archivos del procesamiento con IA (eventos, reintentos, idempotencia).
3. Usar una **cuenta de facturación y un proyecto GCP del proyecto**.
4. Mantener las imágenes de menores en un **bucket privado**.
5. Publicar el sitio en un **dominio propio**.
6. No depender de keys JSON ni de rutas locales.

---

## 2. Estado actual (v1)

```
Formulario en papel + dibujo
        |
        v
Escaneo (JPG)
        |
        +--> subida manual al bucket
        |
        +--> web -> Cloud Run API -> GCS -> Gemini -> BigQuery
        |
        v
index.html + data.js + resumen_ia.js -> GitHub Pages
```

Problemas conocidos:

- La web procesa con Gemini **dentro del mismo request** de subida: si falla o se corta, la imagen queda en GCS pero no en BigQuery.
- Las imágenes subidas directo al bucket **no se procesan**.
- Reintentos pueden duplicar filas en BigQuery.
- El bucket y las imágenes son públicos.
- Proyecto y ruta de key hardcodeados en los scripts.
- `data.js` y `resumen_ia.js` se regeneran a mano.
- No hay monitoreo, alertas ni presupuesto.

---

## 3. Arquitectura propuesta (v2)

```
Web (GitHub Pages / dominio propio)
  │  1. POST /api/upload-url
  ▼
Cloud Run API  ──► URL firmada (V4)
  │  2. PUT directo a GCS
  ▼
GCS bucket privado (uploads/<sede>/...)
  │  3. evento object.finalized
  ▼
Eventarc ──► Cloud Run Processor
  │  4. valida extensión y tamaño
  │  5. descarga la imagen
  │  6. Gemini extrae datos
  │  7. inserta en BigQuery (idempotente)
  ▼
BigQuery post_cronos.encuestas
  │
  ▼
GET /api/data ──► galería / dashboard
```

La misma ruta de procesamiento se usa para:

- subidas desde la web;
- subidas manuales por consola, `gcloud storage cp` o `gsutil`;
- reprocesamientos y migraciones.

### Componentes

| Componente | Servicio | Función |
|---|---|---|
| Web | GitHub Pages | Dashboard, galería y formulario de subida |
| API | Cloud Run | Rate limit, URL firmada / recepción de archivo, lectura de datos |
| Processor | Cloud Run | Procesamiento con Gemini e inserción en BigQuery |
| Eventos | Eventarc | Dispara el processor al finalizar un objeto en GCS |
| Imágenes | Cloud Storage | Bucket privado |
| Datos | BigQuery | Tabla `post_cronos.encuestas` |
| IA | Vertex AI | `gemini-2.5-flash-lite` |
| Secretos | IAM / ADC | Sin keys JSON en el repo |

---

## 4. Flujos

### 4.1 Subida desde la web

1. El navegador valida que sea JPG y que no supere 10 MB.
2. `POST /api/upload-url` con nombre, tipo y tamaño.
3. La API aplica rate limit y devuelve una URL firmada para subir a `uploads/<sede>/<uuid>.jpg`.
4. El navegador hace `PUT` directo a GCS y muestra progreso.
5. GCS emite `object.finalized`.
6. Eventarc invoca el processor.
7. La web consulta `GET /api/data` cada pocos segundos hasta ver la fila nueva (o `GET /api/status/<objeto>`).

Alternativa más simple: mantener `POST /api/upload` multipart, pero sin llamar a Gemini. La API solo guarda en GCS y responde `202`; el processor hace el resto.

### 4.2 Subida directa al bucket

Cualquier objeto nuevo en el bucket dispara el mismo evento. No hace falta pasar por la web.

El processor filtra:

- extensiones `.jpg` y `.jpeg`;
- prefijos permitidos (`uploads/`, `santa_ana/`, etc.);
- objetos internos de migración (`migration/`) para no procesarlos.

### 4.3 Idempotencia

Crear una tabla auxiliar:

```sql
CREATE TABLE IF NOT EXISTS `post_cronos.procesados` (
  object_name STRING,
  generation INT64,
  status STRING,
  error STRING,
  updated_at TIMESTAMP
);
```

Reglas:

- Clave: `object_name + generation`.
- Si ya está `done`, el processor no vuelve a llamar a Gemini.
- Si está `error`, se puede reintentar.
- El `id_encuesta` se deriva del nombre del objeto (por ejemplo, `santa_ana_5334`) para que un reintento no duplique filas.
- La inserción en BigQuery usa `MERGE` o `INSERT ... WHERE NOT EXISTS`.

### 4.4 Errores y reintentos

- Eventarc reintenta ante respuestas 5xx.
- Guardar el error en `procesados.error`.
- Alertar si hay muchos `error` seguidos (Cloud Monitoring).
- Opcional: Pub/Sub con dead-letter topic si se usa notificación de GCS en vez de Eventarc.

---

## 5. Recursos GCP

### 5.1 Proyecto y facturación

Permisos necesarios para la persona que deploya:

- `roles/owner` o `roles/editor` en el proyecto.
- `roles/billing.user` en la cuenta de facturación (para vincularla).
- `roles/resourcemanager.projectCreator` si hay que crear el proyecto.

### 5.2 APIs a habilitar

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  bigquery.googleapis.com \
  aiplatform.googleapis.com \
  eventarc.googleapis.com \
  pubsub.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com
```

### 5.3 Service accounts y roles

| Service account | Roles |
|---|---|
| `post-cronos-api` | `roles/storage.objectAdmin`, `roles/bigquery.dataEditor`, `roles/bigquery.jobUser` |
| `post-cronos-processor` | `roles/storage.objectViewer`, `roles/bigquery.dataEditor`, `roles/bigquery.jobUser`, `roles/aiplatform.user` |

El trigger de Eventarc necesita además:

- `roles/eventarc.eventReceiver`;
- `roles/run.invoker` sobre el servicio processor.

### 5.4 Bucket

- Bucket privado (sin `allUsers`).
- Uniform bucket-level access.
- Región `us-central1` (la misma que BigQuery y Vertex AI).
- Nombre único global, por ejemplo `<PROJECT_ID>-post-cronos-dibujos`.
- Lifecycle opcional para originales temporales.
- Las imágenes se sirven por proxy `/api/img/...` o por URL firmada de lectura.

### 5.5 BigQuery

- Dataset `post_cronos`, región `us-central1`.
- Tabla `encuestas` con el esquema actual.
- Tabla `procesados` para idempotencia.
- Opcional: tabla particionada por fecha si crece el volumen.

### 5.6 Cloud Run

- `post-cronos-api`: público, scale-to-zero, `max-instances` bajo.
- `post-cronos-processor`: privado, invocado por Eventarc, `max-instances` bajo, timeout 300 s.
- CPU y memoria: 1 vCPU / 1 GiB para empezar.
- Variables por entorno, sin secretos en el repo.

### 5.7 Eventarc

```bash
gcloud eventarc triggers create post-cronos-gcs-finalize \
  --location=us-central1 \
  --destination-run-service=post-cronos-processor \
  --destination-run-region=us-central1 \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=<BUCKET>" \
  --service-account=post-cronos-processor@<PROJECT_ID>.iam.gserviceaccount.com
```

### 5.8 Alternativa por lotes (menor costo)

Si el costo importa más que la inmediatez:

- Cloud Scheduler cada 15/60 minutos.
- Cloud Run Job que lista objetos del bucket, procesa los pendientes y actualiza `procesados`.
- No se usa Eventarc.
- La galería tarda en actualizarse hasta la próxima corrida.

---

## 6. Migración desde v1

### Fase 0 — Accesos

- [ ] Confirmar quién es owner del proyecto GCP actual y de la facturación.
- [ ] Obtener permisos de Owner/Editor en el proyecto nuevo.
- [ ] Obtener `roles/billing.user` en la cuenta de facturación nueva.
- [ ] Instalar Google Cloud SDK (`gcloud`) en la máquina de deploy.

### Fase 1 — Proyecto nuevo

- [ ] Crear el proyecto GCP (o usar el existente de la cuenta nueva).
- [ ] Vincular la cuenta de facturación.
- [ ] Habilitar las APIs de la sección 5.2.
- [ ] Crear las service accounts y asignar roles.
- [ ] Configurar presupuesto y alertas.

### Fase 2 — Datos

- [ ] Crear bucket privado en `us-central1`.
- [ ] Copiar imágenes:

```bash
gcloud storage rsync -r gs://post-cronos-dibujos-2060 gs://<BUCKET>
```

- [ ] Crear dataset `post_cronos`.
- [ ] Copiar la tabla:

```bash
bq cp laboratorio-cordoba-2060:post_cronos.encuestas \
  <PROJECT_ID>:post_cronos.encuestas
```

- [ ] Verificar cantidad de filas e imágenes.
- [ ] Actualizar `url_imagen_dibujo` a las URLs nuevas (o al proxy).

### Fase 3 — Servicios

- [ ] Deployar `post-cronos-processor`.
- [ ] Crear el trigger de Eventarc.
- [ ] Deployar `post-cronos-api`.
- [ ] Configurar `ALLOWED_ORIGINS` con el dominio final.
- [ ] Probar subida web, subida directa y reprocesamiento.

### Fase 4 — Web y dominio

- [ ] Actualizar `window.POST_CRONOS_API` en `index.html`.
- [ ] Verificar galería y dashboard con datos en vivo.
- [ ] Configurar el dominio propio (sección 7).
- [ ] Actualizar documentación y links.

### Fase 5 — Cierre

- [ ] Revocar la key vieja y el acceso de la cuenta personal.
- [ ] Archivar el repo/proyecto anterior.
- [ ] Documentar accesos y owners en un gestor de contraseñas.
- [ ] Activar 2FA en GitHub, Google y el registrador del dominio.
- [ ] Probar el runbook desde una máquina limpia.

---

## 7. Dominio propio

### 7.1 Web en GitHub Pages

1. Agregar un archivo `CNAME` en la raíz del repo con el dominio (ej. `postcronos.org`).
2. Configurar DNS:
   - `www` → CNAME a `post-cronos.github.io`.
   - raíz (`@`) → A:
     `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`.
   - IPv6 opcional (AAAA):
     `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153`, `2606:50c0:8003::153`.
3. En GitHub: Settings → Pages → Custom domain.
4. Esperar propagación y activar “Enforce HTTPS”.

Si el DNS está en Cloudflare:

- Los registros de GitHub Pages deben ir en modo **DNS only** (nube gris), no proxied.
- Alternativa: usar Cloudflare Pages para el frontend y dejar GitHub Pages como respaldo.

### 7.2 API con subdominio (opcional)

- Opción simple: usar la URL de Cloud Run (`https://...run.app`).
- Opción con dominio: `api.<dominio>` mediante Cloud Run domain mapping o un HTTPS Load Balancer.
- El Load Balancer tiene costo fijo mensual; para el volumen del proyecto no es necesario al inicio.

### 7.3 CORS

`ALLOWED_ORIGINS` debe incluir exactamente:

```
https://<dominio>
https://www.<dominio>
https://post-cronos.github.io
http://localhost:8765
```

---

## 8. Costos

El gasto real lo concentra **Vertex AI (Gemini)**. Cloud Run con scale-to-zero, GCS y BigQuery son marginales para este volumen.

Medidas de control:

- `gemini-2.5-flash-lite`.
- Achicar la imagen antes de enviarla a Gemini (máx. 1600 px).
- No reprocesar objetos ya procesados.
- `max-instances` bajo en Cloud Run.
- Lifecycle en GCS para originales que no se necesiten.
- Presupuesto con alertas (por ejemplo, USD 10/20/50).
- Revisar logs y métricas semanalmente.

Eventarc en tiempo real vs. lote:

- Tiempo real: mejor experiencia, costo de eventos y una invocación extra.
- Lote: más barato, pero la galería se actualiza con demora.
- Para el volumen de un colegio, la diferencia es menor; priorizar confiabilidad.

---

## 9. Seguridad y privacidad

- Bucket privado; nunca exponer imágenes de menores con ACL públicas.
- Servir imágenes por proxy autenticado con service account o URL firmada de corta duración.
- Revisar consentimientos de imagen de los participantes.
- Rate limit y límite de tamaño en la API.
- Validar MIME y magic bytes del JPG.
- Sin keys JSON en el repo; usar ADC y service accounts adjuntas.
- 2FA en GitHub, Google y registrador del dominio.
- Revisar logs de acceso y errores.
- Definir política de retención de imágenes y datos.

---

## 10. Checklist de aceptación

- [ ] Subida desde la web con progreso y mensaje de “procesando”.
- [ ] Subida directa al bucket procesada automáticamente.
- [ ] Imagen inválida o mayor a 10 MB rechazada.
- [ ] Reintento no duplica filas.
- [ ] Error de Gemini registrado y reintentable.
- [ ] Galería y dashboard actualizados con datos en vivo.
- [ ] Dominio propio con HTTPS.
- [ ] CORS restringido al dominio.
- [ ] Bucket privado y proxy funcionando.
- [ ] Presupuesto y alertas activos.
- [ ] Key vieja revocada.

---

## 11. Decisiones pendientes

- [ ] Nombre exacto del dominio y registrador.
- [ ] ¿Web en GitHub Pages con dominio propio o Cloudflare Pages?
- [ ] ¿Procesamiento en tiempo real (Eventarc) o por lotes (Cloud Scheduler)?
- [ ] ¿Subida directa con URL firmada o multipart a la API?
- [ ] ¿La subida es pública o requiere clave/captcha?
- [ ] Política de retención de imágenes y datos.
- [ ] ¿Se conserva `data.js` estático como respaldo o se elimina?

---

## 12. Comandos de referencia

```bash
# Proyecto
gcloud config set project <PROJECT_ID>

# Service accounts
gcloud iam service-accounts create post-cronos-api --display-name="Post-Cronos API"
gcloud iam service-accounts create post-cronos-processor --display-name="Post-Cronos Processor"

# Bucket privado
gcloud storage buckets create gs://<BUCKET> \
  --location=us-central1 \
  --uniform-bucket-level-access

# Cloud Run API
gcloud run deploy post-cronos-api \
  --source backend/api \
  --region us-central1 \
  --allow-unauthenticated \
  --service-account post-cronos-api@<PROJECT_ID>.iam.gserviceaccount.com

# Cloud Run Processor
gcloud run deploy post-cronos-processor \
  --source backend/processor \
  --region us-central1 \
  --no-allow-unauthenticated \
  --service-account post-cronos-processor@<PROJECT_ID>.iam.gserviceaccount.com

# Eventarc
gcloud eventarc triggers create post-cronos-gcs-finalize \
  --location=us-central1 \
  --destination-run-service=post-cronos-processor \
  --destination-run-region=us-central1 \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=<BUCKET>" \
  --service-account=post-cronos-processor@<PROJECT_ID>.iam.gserviceaccount.com
```

---

## 13. Código en este repositorio

- `index.html`, `data.js`, `resumen_ia.js`, `logo.png`: frontend.
- `backend/`: API base (v1, síncrona) que se refactoriza a los servicios `api` y `processor` de la sección 3.
- `scripts/legacy/`: scripts de procesamiento y migración de la v1.
- `docs/post-cronos-infraestructura.md`: documento técnico de la v1.

El próximo paso de código es reemplazar `backend/main.py` por:

- `backend/api/`: endpoints públicos (`/api/data`, `/api/img`, `/api/upload-url`, `/api/status`).
- `backend/processor/`: consumidor de eventos de GCS (Eventarc) con Gemini + BigQuery.
- `backend/common.py`: configuración, prompt, idempotencia y acceso a GCP.

## 14. Guías para frontend

- `docs/integracion-frontend.md` — contrato técnico completo (endpoints, JSON, errores, CORS).
- `docs/instructivo-frontend-simple.md` — paso a paso para alguien con poca experiencia.
- `docs/ejemplo-subida.html` — ejemplo mínimo de subida con progreso y polling.

## 15. Referencias

- Repo v1: https://github.com/post-cronos/post-cronos
- Repo v2: https://github.com/post-cronos/post-cronos-v2
- Sitio v1: https://post-cronos.github.io/post-cronos/
- Documento técnico v1: `docs/post-cronos-infraestructura.md`
