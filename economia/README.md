# App `economia` — API de Economía para jóvenes

Backend (solo API, sin frontend) que explica **38 conceptos de economía y finanzas personales**
en lenguaje simple y los conecta con **datos económicos de Chile en vivo** (UF, dólar, TPM, etc.).
Los conceptos, ejemplos, prerrequisitos y fuentes salen del PDF *"Conceptos financieros:
prerrequisitos y fuentes"*.

No agrega dependencias: usa solo Django y la biblioteca estándar de Python.

## Cómo usarla

```bash
source .venv/bin/activate              # o el equivalente en tu sistema
python manage.py runserver             # http://127.0.0.1:8000/api/
python manage.py test economia         # 88 pruebas, no necesitan internet
```

Primera prueba real (comprueba que tu computador llega a la API de indicadores):

```bash
curl "http://127.0.0.1:8000/api/salud/?probar_fuente=1"
```

Abre `http://127.0.0.1:8000/api/` en el navegador: la API se describe sola, con un ejemplo por ruta.

## Rutas

| Ruta | Para qué sirve |
|---|---|
| `GET /api/` | Mapa de la API con ejemplos |
| `GET /api/conceptos/` | Los 38 conceptos. Filtros: `nivel`, `categoria`, `estado` (A/B/C), `q` (texto) |
| `GET /api/conceptos/{slug}/` | Ficha completa: definición, ejemplo, prerrequisitos, qué desbloquea, fuentes y datos en vivo relacionados (`?en_vivo=0` para omitirlos) |
| `GET /api/ruta-aprendizaje/` | En qué orden estudiar. `?hasta={slug}` entrega solo lo necesario para llegar a ese concepto |
| `GET /api/fuentes/` | Fuentes consultadas y significado de A, B y C |
| `GET /api/indicadores/` | UF, dólar, euro, TPM, IPC, Imacec, desempleo, UTM, bitcoin y cobre, con explicación simple |
| `GET /api/indicadores/{codigo}/` | Un indicador con su variación y valores anteriores (`?ultimos=30`) |
| `GET /api/herramientas/convertir/` | `?de=usd&a=clp&monto=100` (monedas: `clp`, `uf`, `usd`, `eur`) con valores en vivo |
| `GET /api/herramientas/interes-compuesto/` | `?capital=100000&tasa=10&anios=2` |
| `GET /api/herramientas/tasa-real/` | `?nominal=5&inflacion=4` |
| `GET /api/salud/` | Estado del servidor (`?probar_fuente=1` prueba también la API externa) |

Reglas generales:
- Todo responde JSON en UTF-8. Los errores siempre tienen la forma
  `{"error": {"codigo": "...", "mensaje": "..."}}` (400 parámetro inválido, 404 no existe, 405 método, 503 fuente caída).
- Los números van **sin separador de miles y con punto decimal**: `1000000.5`, no `1.000.000,5`.
  Un valor como `100.000` se rechaza a propósito (en Chile significa cien mil, pero aquí valdría 100).
- Para el frontend: todas las rutas del `/api/` envían cabeceras CORS (`ECONOMIA_CORS_ORIGEN`).

## Verificación del contenido (A, B, C)

Cada concepto conserva el estado del PDF, y la API lo entrega junto a una frase para el lector:
**A** verificado en fuente oficial, **B** parcialmente, **C** solo bibliografía (Mankiw, sin contrastar en línea).
El PDF pide contrastar los C antes de darlos por definitivos; el frontend puede mostrar la insignia.

## Datos en vivo

- Fuente: [mindicador.cl](https://mindicador.cl/api) (pública, sin clave).
- Caché de 10 minutos. Si la fuente cae, se sigue sirviendo la última respuesta con `cache.obsoleta: true`
  y un `aviso`. Si no hay nada guardado, se responde 503.
- Cada indicador trae `fecha_dato`, `dias_desde_el_dato` y `dato_atrasado`: algunos datos mensuales
  (IPC, Imacec, desempleo) se publican con retraso y no deben presentarse como "de hoy".
- Las frases `que_es`, `por_que_importa` y `lectura_simple` de cada indicador **no vienen del PDF**
  (están en `indicadores.py`): conviene que alguien del equipo las revise.

## Ajustes opcionales (`settings.py`)

`ECONOMIA_FUENTE_URL` (también como variable de entorno), `ECONOMIA_CACHE_SEGUNDOS` (600),
`ECONOMIA_TIMEOUT_SEGUNDOS` (8), `ECONOMIA_CORS_ORIGEN` (`'*'`).

## Mapa del código

| Archivo | Responsabilidad |
|---|---|
| `data/conceptos.json`, `data/fuentes.json` | Contenido del PDF (38 conceptos, 17 fuentes) |
| `conceptos.py` | Carga, búsqueda, prerrequisitos y ruta de aprendizaje |
| `indicadores.py` | Catálogo de indicadores, cliente de la API externa y caché |
| `herramientas.py` | Calculadoras (funciones puras, con `Decimal`) |
| `views.py` / `urls.py` | Rutas, validación de parámetros y respuestas |
| `respuestas.py`, `middleware.py`, `formato.py` | JSON y errores, CORS, formato chileno de números |
| `tests/` | 88 pruebas; los datos de internet se simulan con `tests/fixtures/` |
