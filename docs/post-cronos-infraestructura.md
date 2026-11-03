# Post-Cronos: Córdoba 2060 — Documento técnico de infraestructura

> Documento pensado para ser leído por una persona o por un agente de IA.
> Fuente: repositorio `github.com/post-cronos/post-cronos` (rama `master`) + `AGENTS.md`.
> Última actualización: 2026-10-29. Los datos marcados como "A confirmar" no están en el repo.

---

## 1. Resumen ejecutivo

Post-Cronos es un proyecto participativo: niños y adolescentes dibujan cómo imaginan Córdoba en 2060. Cada participante completa un formulario en papel, se escanea el dibujo, se sube a Google Cloud Storage, Gemini extrae los datos estructurados, se guardan en BigQuery y se publican en una galería/dashboard web estática.

Estado actual: **prototipo funcional operado desde una cuenta personal**. No hay documentación de accesos, el sitio vive en GitHub Pages, las credenciales de Google están en un archivo JSON local con ruta hardcodeada, y las imágenes (de menores) son públicas. La migración a cuentas del proyecto es la prioridad.

---

## 2. Arquitectura actual

```
Formulario en papel + dibujo
        |
        v
  Escaneo (archivo de imagen)
        |
        v
  Google Cloud Storage  gs://post-cronos-dibujos-2060
  (objetos publicos via ACL, URL https://storage.googleapis.com/...)
        |
        v
  Gemini 2.5 Flash Lite (Vertex AI)  ->  extrae datos estructurados
        |
        v
  BigQuery  laboratorio-cordoba-2060.post_cronos.encuestas
        |
        +--> generate_data.py     -> data.js     (window.DATA)
        +--> analisis_tendencias.py -> resumen_ia.js (window.RESUMEN)
        |
        v
  index.html (estatico, sin backend)  ->  GitHub Pages
```

No hay servidor, base de datos propia ni API. La web es 100% estática y consume dos archivos JS generados por scripts Python que corren **manualmente en una máquina local**.

---

## 3. Componentes y configuración

### 3.1 Hosting — GitHub Pages
- Repo: `post-cronos/post-cronos`, rama `master`.
- Publica `index.html`, `logo.png`, `data.js`, `resumen_ia.js`.
- No hay build step ni CI: el deploy es el push a `master`.
- Dominio actual: `https://post-cronos.github.io/post-cronos/`.

### 3.2 Storage — Google Cloud Storage
- Bucket: `post-cronos-dibujos-2060`, región `us-central1`.
- Contiene las imágenes de los dibujos.
- Los objetos se hicieron públicos individualmente con ACL (`make_public.py`), URL: `https://storage.googleapis.com/post-cronos-dibujos-2060/<archivo>`.
- **Riesgo**: son imágenes de menores en un bucket público y enumerable.

### 3.3 Base de datos — BigQuery
- Proyecto GCP: `laboratorio-cordoba-2060`.
- Dataset/tabla: `post_cronos.encuestas`.
- Columnas usadas por los scripts:

| Columna | Tipo | Uso |
|---|---|---|
| `id_encuesta` | string | ID único (ej. `IMG_5334`) |
| `edad` | integer | Edad del participante |
| `genero` | string | `Masculino`, `Femenino`, `No binario`, `Otro`, `No responder` |
| `colegio` | string | Colegio |
| `ciudad_barrio` | string | Ciudad/barrio |
| `eje` | string | Uno o varios separados por coma (ej. `"Moda, Tecnología"`) |
| `url_imagen_dibujo` | string | URL HTTPS pública del dibujo |
| `descripcion_audio_o_ia` | string | Interpretación del dibujo por Gemini |
| `descripcion_final_texto` | string | Texto final / diseño propuesto |

### 3.4 IA — Vertex AI Gemini
- Modelo: `gemini-2.5-flash-lite`, location `us-central1`.
- Dos usos:
  1. `process_with_gemini.py` (no está en el repo): lee imágenes de GCS y extrae datos para BigQuery.
  2. `analisis_tendencias.py`: analiza la tabla y genera `resumen_ia.js` con tendencias, insights por eje y recomendaciones.
- El prompt debe pedir explícitamente buscar **X o tildes** en lugar de inferir género/eje.

### 3.5 Credenciales (estado actual, a migrar)
- Todos los scripts hacen:
  ```python
  os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\Post cronos\laboratorio-cordoba-2060-9fc2ad8ce3c5.json'
  ```
- Es una **service account key** guardada en el disco de una persona, con ruta absoluta hardcodeada en el código.
- `.gitignore` excluye `laboratorio-cordoba-2060-*.json`, `.env`, `.venv/`.
- No hay variables de entorno ni secreto en GitHub Actions.

---

## 4. Flujo operativo (runbook actual)

1. Escanear formulario + dibujo.
2. Subir la imagen a `gs://post-cronos-dibujos-2060`.
3. Correr `process_with_gemini.py` (no versionado) → inserta fila en BigQuery.
4. Correr `generate_data.py` → regenera `data.js`.
5. Correr `analisis_tendencias.py` → regenera `resumen_ia.js` (opcional, consume cuota de Gemini).
6. `git commit` + `git push` a `master` → GitHub Pages publica.
7. Las URLs de imágenes se migraron de `gs://` a `https://` con `update_urls_bq.py`.

Nota: el código asume Python con venv local (`.venv\Scripts\python`), Windows, y los archivos de salida se escriben junto al script.

---

## 5. Deuda técnica y riesgos

| Riesgo | Detalle | Prioridad |
|---|---|---|
| Credenciales personales | Service account key en `D:\...` hardcodeada en 8+ scripts | Alta |
| Propiedad de cuentas | Repo, proyecto GCP y (a confirmar) dominio a nombre de una persona | Alta |
| Imágenes de menores públicas | Bucket con ACL público, URLs enumerables | Alta (legal/privacidad) |
| Script faltante | `process_with_gemini.py` se menciona pero no está en el repo | Media |
| Sin CI/CD | `data.js` y `resumen_ia.js` se generan a mano y se commitean | Media |
| Sin backups | BigQuery/GCS sin política de respaldo documentada | Media |
| Rutas hardcodeadas | `D:\Post cronos\...` rompe en cualquier otra máquina | Media |
| Sin tests | No hay tests ni validación de esquema | Baja |

---

## 6. Migración propuesta (cuentas del proyecto)

Objetivo: que nada dependa de una cuenta personal y que cualquier integrante pueda operar el proyecto.

### 6.1 Arquitectura destino

```
Dominio del proyecto
   |-- DNS + CDN + hosting  ->  Cloudflare (o Netlify/Vercel)
   |-- Correo               ->  Google Workspace o Zoho Mail
   |-- Codigo               ->  GitHub Organization "post-cronos"
   |-- Datos/IA             ->  Proyecto GCP del proyecto + service account propia
```

### 6.2 Pasos

**Fase 1 — Código (sin downtime)**
- [ ] Crear GitHub Organization (plan Free) a nombre del proyecto.
- [x] Migrar el repo a la cuenta del proyecto: `post-cronos/post-cronos` (historial conservado).
- [ ] Dar roles: owners del proyecto, `maintain`/`write` a desarrollo.
- [ ] Quitar credenciales hardcodeadas y usar `GOOGLE_APPLICATION_CREDENTIALS` por variable de entorno.
- [ ] Agregar `process_with_gemini.py` al repo.
- [ ] Agregar `requirements.txt` y un README de setup.

**Fase 2 — Google Cloud**
- [ ] Crear (o adoptar) un proyecto GCP del proyecto, con facturación del proyecto.
- [ ] Crear service account con roles mínimos: `roles/bigquery.dataEditor`, `roles/bigquery.jobUser`, `roles/storage.objectAdmin`, `roles/aiplatform.user`.
- [ ] Descargar la key una sola vez y distribuirla por gestor de contraseñas (nunca por WhatsApp/mail).
- [ ] Migrar el bucket y el dataset (mismo nombre o nuevo + actualizar scripts).
- [ ] Revisar ACLs: idealmente bucket privado + URLs firmadas o proxy.
- [ ] Configurar backup/export de BigQuery a GCS.

**Fase 3 — Dominio, hosting y correo**
- [ ] Transferir/crear el dominio en una cuenta del proyecto (registrador + Cloudflare).
- [ ] Cloudflare: DNS, HTTPS, CDN. Hosting en Cloudflare Pages conectado al repo (deploy automático en push) o mantener Pages de GitHub con dominio propio.
- [ ] Correo: elegir proveedor y crear casillas del proyecto.
- [ ] Cargar registros DNS de correo: `MX`, `SPF` (TXT), `DKIM` (TXT), `DMARC` (TXT), y `mail.` si hay webmail.
- [ ] Verificar envío/recepción y documentar accesos.

**Fase 4 — Cierre**
- [ ] Documento de accesos (quién es owner de qué) en el repo o gestor de contraseñas.
- [ ] 2FA obligatorio en GitHub, Google y Cloudflare.
- [ ] Rotar y revocar la key personal anterior.
- [ ] Probar el runbook completo desde una máquina limpia.

### 6.3 Registros DNS típicos

| Tipo | Nombre | Valor | Para |
|---|---|---|---|
| `A` / `CNAME` | `@` / `www` | hosting | Sitio |
| `CNAME` | `app` | hosting | Futuras apps |
| `MX` | `@` | proveedor de correo | Correo |
| `TXT` | `@` | `v=spf1 ...` | SPF |
| `TXT` | `selector._domainkey` | clave DKIM | DKIM |
| `TXT` | `_dmarc` | `v=DMARC1; ...` | DMARC |
| `CNAME` | `mail` | proveedor | Webmail/IMAP |

### 6.4 Datos que faltan relevar

- Dominio exacto y dónde está registrado.
- Quién es owner del proyecto GCP `laboratorio-cordoba-2060` y de la facturación.
- Cantidad de casillas de correo y presupuesto (Google Workspace vs Zoho gratis).
- Herramienta con la que se está rehaciendo el sitio (HTML estático, WordPress, Wix, etc.).
- Autorizaciones/consentimientos para publicar imágenes de menores.

---

## 7. Recomendación práctica

1. **Cloudflare** como centro de DNS: gratis, permite manejar web, subdominios y correo en un solo lugar sin ataduras al hosting.
2. **Hosting**: Cloudflare Pages (o Netlify/Vercel) conectado al repo → deploy automático. Si el sitio se rehace en WordPress/Wix, dejar el DNS en Cloudflare y solo apuntar el dominio.
3. **Correo**: Google Workspace (~USD 7/usuario/mes) si se busca solidez; Zoho Mail (plan gratis hasta 5 cuentas) si el presupuesto es cero.
4. **Google Cloud**: proyecto y service account del proyecto, roles mínimos, sin keys en el repo ni en discos personales.
5. **Privacidad**: sacar las imágenes de menores de un bucket público antes de escalar el proyecto.

---

## 8. Cómo usar este documento (para el agente de IA)

- Este archivo describe el estado real del repo `post-cronos/post-cronos` al 2026-11-02.
- "A confirmar" significa que el dato no está en el repositorio y debe preguntarse a las personas.
- No asumir que existen tests, CI, backend ni base de datos propia: no existen.
- Antes de proponer cambios, verificar los nombres exactos de bucket (`post-cronos-dibujos-2060`), proyecto (`laboratorio-cordoba-2060`), tabla (`post_cronos.encuestas`) y modelo (`gemini-2.5-flash-lite`).
- Las rutas `D:\Post cronos\...` son locales de una persona y no deben replicarse.
