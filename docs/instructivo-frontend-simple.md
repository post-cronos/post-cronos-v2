# Instructivo simple: conectar la página con la infraestructura

Para la persona que arma la página. **No hace falta saber Google Cloud.**

---

## 1. Qué tiene que hacer la página

1. Mostrar los datos que vienen de una dirección (la API).
2. Permitir subir un archivo JPG.
3. Mostrar un mensaje mientras la IA lo procesa.

---

## 2. La única dirección que necesitás

La API es una dirección web que devuelve datos. Te la pasa infraestructura. Se configura así, **antes** de tu código:

```html
<script>
  window.POST_CRONOS_API = "https://post-cronos-api-XXXXX-uc.a.run.app";
</script>
```

- Sin barra `/` al final.
- Tiene que ser `https://` (salvo `localhost`).
- Si esa línea no está, la página usa los datos de ejemplo de `data.js`.

---

## 3. Cómo saber si la API funciona

Abrí estas direcciones en el navegador:

| Dirección | Qué tiene que mostrar |
|---|---|
| `.../health` | `{"ok": true}` |
| `.../api/data` | Una lista de participantes |

Si no cargan, avisale a infraestructura. No es un problema de tu código.

---

## 4. Qué datos llegan

Cada participante llega así:

```json
{
  "id": "santa_ana_5334",
  "edad": 11,
  "genero": "Femenino",
  "ciudad_barrio": "Villa Belgrano",
  "colegio": "Instituto Santa Ana",
  "eje": "Moda, Tecnologia",
  "img": "https://.../api/img/...",
  "interp": "El dibujo muestra...",
  "diseno": "Texto escrito por el participante"
}
```

Cosas importantes:

- `img` ya es una dirección lista para usar en `<img src="...">`.
- `eje` puede tener varios temas separados por coma.
- Algunos campos pueden ser `null` (vacío).
- No hay que pedir imágenes por separado: ya vienen en `img`.

Para mostrar la lista:

```js
fetch(window.POST_CRONOS_API + "/api/data")
  .then((r) => r.json())
  .then((participantes) => {
    // acá dibujás las tarjetas
  });
```

---

## 5. Cómo subir un JPG

La subida tiene 3 pasos:

1. Pedir permiso a la API (`/api/upload-url`).
2. Enviar el archivo a la dirección que devuelve.
3. Esperar a que la IA termine (`/api/status`).

Copiá y pegá esta función:

```js
async function subirJpg(file, school, onProgress) {
  const api = window.POST_CRONOS_API.replace(/\/$/, "");

  const pedido = await fetch(api + "/api/upload-url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      filename: file.name,
      contentType: "image/jpeg",
      size: file.size,
      school: school
    })
  });

  if (!pedido.ok) {
    const error = await pedido.json().catch(() => ({}));
    throw new Error(error.detail || "No se pudo preparar la subida");
  }

  const { uploadUrl, objectName } = await pedido.json();

  await new Promise((listo, fallo) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", "image/jpeg");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) listo();
      else fallo(new Error("Error al subir el archivo"));
    };
    xhr.onerror = () => fallo(new Error("Error de conexión"));
    xhr.send(file);
  });

  return objectName;
}
```

Y esta para esperar el resultado:

```js
async function esperarResultado(objectName) {
  const api = window.POST_CRONOS_API.replace(/\/$/, "");
  const url = api + "/api/status?object=" + encodeURIComponent(objectName);

  for (let i = 0; i < 30; i++) {
    const respuesta = await fetch(url, { cache: "no-store" });
    if (respuesta.ok) {
      const datos = await respuesta.json();
      if (datos.status === "done") return datos.record;
      if (datos.status === "error") throw new Error("No se pudo procesar");
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error("Está tardando demasiado");
}
```

Uso:

```js
const archivo = document.getElementById("file").files[0];

subirJpg(archivo, "santa_ana", (porcentaje) => {
  document.getElementById("progress").value = porcentaje;
})
  .then((objectName) => {
    document.getElementById("status").textContent = "Procesando con IA...";
    return esperarResultado(objectName);
  })
  .then((registro) => {
    document.getElementById("status").textContent = "¡Listo!";
    console.log(registro);
  })
  .catch((error) => {
    document.getElementById("status").textContent = error.message;
  });
```

---

## 6. Errores comunes

| Mensaje / problema | Qué significa | Qué hacer |
|---|---|---|
| `Subida no configurada` | Falta `window.POST_CRONOS_API` | Pedir la URL a infraestructura |
| `Failed to fetch` | URL mal escrita o CORS | Avisar a infraestructura |
| `429` | Demasiadas subidas | Esperar unos minutos |
| `413` | Archivo mayor a 10 MB | Usar un JPG más chico |
| `400` | No es un JPG válido | Revisar el archivo |
| Botón deshabilitado | No hay archivo elegido | Elegir un JPG primero |

---

## 7. Qué NO hacer

- No poner claves de Google, archivos `.json` de service account ni contraseñas.
- No cambiar la dirección de la API por tu cuenta.
- No subir archivos que no sean JPG.
- No abrir el HTML con doble clic (`file://`). Usar un servidor local:

```bash
python -m http.server 8765
```

Y abrir `http://localhost:8765`.

---

## 8. Cómo trabajar sin backend

La página funciona con datos de ejemplo (`data.js`) aunque la API no esté lista. Sirve para maquetar y probar el diseño.

---

## 9. Checklist

- [ ] `window.POST_CRONOS_API` configurado.
- [ ] `/health` y `/api/data` responden en el navegador.
- [ ] La galería muestra los datos.
- [ ] Las imágenes se ven.
- [ ] Se elige un JPG y aparece la vista previa.
- [ ] La barra de progreso avanza.
- [ ] Aparece “Procesando con IA…”.
- [ ] Al terminar, aparece el dibujo nuevo.
- [ ] Los errores muestran un mensaje claro.

---

## 10. Si algo no funciona, pedile a infraestructura

- La URL de la API.
- El origen exacto de tu página (ej. `https://post-cronos.github.io`).
- El mensaje de error y una captura.
- Qué paso hiciste y qué esperabas que pase.
