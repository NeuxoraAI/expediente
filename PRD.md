# PRD — Expediente Vivo

**Versión:** 1.0  
**Estado:** Borrador  
**Fecha:** 2026-05-23  
**Audiencia:** Equipo de desarrollo

---

## 1. Visión general

Expediente Vivo es una plataforma multiagente de gestión de expedientes clínicos. Su propósito es eliminar la carga manual de documentación médica mediante agentes de IA especializados que transcriben, estructuran y consultan la información clínica de cada paciente.

El médico interactúa con un único punto de entrada — el agente Orquestador — a través de un chat. Los demás agentes operan en segundo plano, delegados por el Orquestador, sin que el médico tenga que conocer su existencia ni su funcionamiento interno.

Expediente Vivo es una plataforma independiente. No depende de OpenCode, Claude Code ni ningún agente o IDE externo para operar.

---

## 2. Problema

Los sistemas de expedientes médicos digitales actuales tienen un problema estructural: tratan los documentos como archivos estáticos que el médico debe buscar, abrir y leer manualmente en cada consulta. No hay acumulación inteligente de conocimiento. No hay síntesis. El médico que atiende a un paciente por tercera vez tiene que reconstruir el historial desde cero en cada visita.

Además, la carga de captura de información recae enteramente sobre el médico: transcribir, organizar, estructurar. Esa fricción hace que los sistemas se abandonen.

---

## 3. Solución

Con cada consulta, el sistema genera automáticamente dos documentos por paciente:

- **Formato Crudo** — captura fiel de todo lo que ocurrió en la consulta (voz transcrita, imagen o PDF analizado), sin filtrar ni interpretar.
- **Formato Médico** — información clínicamente relevante de esa consulta, organizada según la plantilla que el médico definió, revisada y aprobada por él antes de ser guardada como documento definitivo.

Ambos documentos se acumulan consulta a consulta en la carpeta del paciente. Cuando el médico necesita información de consultas anteriores, el agente Investigador accede a esos documentos y sintetiza la respuesta directamente en el chat.

El médico habla, revisa, aprueba y pregunta. Los agentes hacen el resto.

---

## 4. Usuarios

**Usuario principal:** médico. Es el único actor humano del sistema. Interactúa exclusivamente a través del chat con el Orquestador.

Acciones que realiza el médico:
- Iniciar la captura de una consulta (voz, imagen o PDF).
- Revisar el Formato Crudo generado.
- Solicitar al Orquestador que genere el Formato Médico.
- Revisar el borrador del Formato Médico y confirmar su guardado definitivo.
- Consultar información de consultas previas de un paciente vía chat.

---

## 5. Entradas soportadas

El sistema acepta tres tipos de entrada desde la consulta médica:

| Tipo | Descripción | Agente responsable |
|------|-------------|-------------------|
| Voz | Grabación de audio de la consulta | Whisper |
| Imagen | Fotografías de documentos, estudios, recetas previas | Scanner |
| PDF | Documentos clínicos digitales, resultados de laboratorio, referencias médicas | Scanner |

Whisper y Scanner son funcionalmente análogos: reciben tipos de entrada distintos y producen el mismo tipo de salida — un archivo de Formato Crudo.

---

## 6. Arquitectura de datos

### 6.1 Decisión de base de datos

Para el MVP, la base de datos es un sistema de archivos markdown local, organizado por paciente. No se utiliza base de datos vectorial.

**Justificación:** el agente Investigador trabaja con documentos completos y bien estructurados, no con fragmentos. A escala de beta, la lectura directa de archivos es suficiente y elimina infraestructura adicional.

**Migración a ChromaDB vectorial:** cuando la base supere los 500 pacientes y la lectura completa de archivos por paciente se vuelva ineficiente. La estructura de archivos está diseñada para que esa migración sea limpia.

### 6.2 Estructura de archivos

```
expedientes/
├── medico/
│   └── plantilla.md                        # Plantilla del médico — aplica a todos los pacientes
├── pacientes/
│   └── {paciente_id}/
│       ├── index.md                         # Catálogo de todas las consultas del paciente
│       ├── log.md                           # Registro de operaciones — append-only
│       ├── Formato crudo/
│       │   ├── YYYY-MM-DD_consulta.md       # Un archivo por consulta
│       │   └── ...
│       └── Formato médico/
│           ├── YYYY-MM-DD_consulta.md       # Un archivo por consulta
│           └── ...
├── index_global.md                          # Lista de todos los pacientes registrados
└── AGENTS.md                               # Schema del sistema y convenciones
```

Cada par `Formato crudo/YYYY-MM-DD_consulta.md` y `Formato médico/YYYY-MM-DD_consulta.md` corresponde a la misma consulta. La fecha en el nombre de archivo es la clave que los vincula.

### 6.3 Frontmatter YAML

Obligatorio en cada archivo de Formato Crudo y Formato Médico:

```yaml
---
paciente_id: P-001
medico_id: M-001
fecha_consulta: 2026-05-22
numero_consulta: 2
tipo_entrada: voz          # voz | imagen | pdf
agente_origen: whisper     # whisper | scanner
tipo_documento: crudo      # crudo | medico
---
```

### 6.4 index.md del paciente

Catálogo de todas las consultas del paciente. Lo actualiza el Formateador cada vez que guarda un Formato Médico definitivo.

```markdown
# Expediente — Paciente P-001

| # | Fecha | Entrada | Motivo | Archivos |
|---|-------|---------|--------|---------|
| 1 | 2026-03-10 | voz | Revisión general | [crudo](...) · [médico](...) |
| 2 | 2026-05-22 | pdf | Seguimiento hipertensión | [crudo](...) · [médico](...) |
```

### 6.5 log.md del paciente

Un archivo por paciente, dentro de su carpeta. El Orquestador es el único que escribe en él. Es append-only: ninguna entrada existente se modifica.

Cada entrada documenta el qué, dónde y por qué de cada operación realizada por cualquier agente:

```markdown
## 2026-05-22 14:35 — Creación de Formato Crudo

- **Agente:** Whisper
- **Qué:** Transcripción de audio de consulta
- **Dónde:** Formato crudo/2026-05-22_consulta.md
- **Por qué:** Entrada de voz recibida para consulta del día

---

## 2026-05-22 15:10 — Creación de Formato Médico

- **Agente:** Formateador
- **Qué:** Transformación de Formato Crudo a Formato Médico definitivo
- **Dónde:** Formato médico/2026-05-22_consulta.md
- **Por qué:** Borrador aprobado por el médico

---
```

### 6.6 Regla de inmutabilidad

Una vez que un archivo de Formato Crudo o Formato Médico es guardado como definitivo, ningún agente puede modificarlo. Los agentes solo crean archivos nuevos. La única excepción son `index.md` y `log.md`, que crecen en modo append.

---

## 7. Arquitectura de agentes

### 7.1 Stack tecnológico

| Componente | Tecnología |
|------------|-----------|
| Lenguaje | Python |
| Framework de agentes | LangGraph |
| Orquestador | Modelo pesado (GPT-4o / Claude Opus) |
| Subagentes | Modelos ligeros (Kimi / DeepSeek) |
| Whisper | Whisper API (OpenAI) o Whisper local |
| Scanner | Modelo de visión (GPT-4o Vision o equivalente) |

LangGraph permite modelar el sistema como un grafo de nodos donde cada nodo opera con su propio modelo. Es necesario para mezclar el modelo pesado del Orquestador con los modelos ligeros de los subagentes, y para manejar el estado de sesión conversacional del Investigador.

### 7.2 Mapa de agentes

```
ORQUESTADOR (modelo pesado)
├── CREADOR       — inicializa la carpeta de un paciente nuevo
├── WHISPER       — transcribe audio a Formato Crudo
├── SCANNER       — analiza imagen o PDF a Formato Crudo
├── FORMATEADOR   — transforma Formato Crudo a Formato Médico
└── INVESTIGADOR  — responde preguntas del médico desde el Formato Médico
```

---

### 7.3 Especificación de agentes

#### ORQUESTADOR

**Modelo:** pesado (GPT-4o / Claude Opus)  
**Rol:** punto de entrada único. Recibe todas las instrucciones del médico, decide qué agente activar, y registra cada operación en el `log.md` del paciente correspondiente.

**Árbol de decisión:**

| Situación | Acción |
|-----------|--------|
| Entrada nueva + paciente sin carpeta | Activa Creador → luego Whisper o Scanner |
| Entrada nueva + paciente existente | Activa Whisper o Scanner directamente |
| Médico solicita formatear el Formato Crudo | Activa Formateador |
| Médico hace una pregunta sobre consultas previas | Activa Investigador |
| Tarea simple (listar pacientes, mostrar index.md) | La ejecuta directamente |

**Responsabilidades adicionales:**
- Es el único agente que escribe en `log.md` — registra el qué, dónde y por qué de cada operación delegada.
- Notifica al médico cuando un agente completa su tarea.
- Transmite la confirmación del médico al Formateador para el guardado definitivo.

---

#### CREADOR

**Modelo:** ligero (Kimi / DeepSeek)  
**Activación:** automática, cuando el Orquestador detecta una entrada para un paciente sin carpeta.  
**Rol:** inicializar la estructura de directorios de un paciente nuevo.

**Output — estructura que crea:**

```
pacientes/{paciente_id}/
├── index.md          # Vacío
├── log.md            # Vacío
├── Formato crudo/    # Carpeta vacía
└── Formato médico/   # Carpeta vacía
```

Una vez creada la estructura, confirma al Orquestador para que este active Whisper o Scanner.

**Input:** `paciente_id` + `medico_id`  
**Output:** estructura de carpetas inicializada + confirmación al Orquestador

---

#### WHISPER

**Modelo:** Whisper API (OpenAI) o Whisper local  
**Activación:** por el Orquestador, cuando la entrada es audio.  
**Rol:** transcribir el audio de la consulta de forma literal y crear el archivo de Formato Crudo.

**Comportamiento:**
- Transcribe todo el audio sin filtrar ni interpretar.
- Crea un archivo nuevo: `Formato crudo/YYYY-MM-DD_consulta.md`.
- Nunca modifica archivos existentes.
- El archivo generado es inmutable.

**Input:** audio de la consulta + `paciente_id`  
**Output:** `Formato crudo/YYYY-MM-DD_consulta.md` (nuevo archivo)

---

#### SCANNER

**Modelo:** modelo de visión (GPT-4o Vision o equivalente)  
**Activación:** por el Orquestador, cuando la entrada es imagen o PDF.  
**Rol:** extraer y estructurar el contenido de la entrada visual y crear el archivo de Formato Crudo.

**Comportamiento:**
- Para imágenes: describe y extrae todo el contenido visible de forma estructurada.
- Para PDFs: extrae y organiza todo el texto e información presente.
- No interpreta ni filtra — solo extrae lo que hay.
- Crea un archivo nuevo: `Formato crudo/YYYY-MM-DD_consulta.md`.
- Nunca modifica archivos existentes.
- El archivo generado es inmutable.

**Input:** imagen o PDF + `paciente_id`  
**Output:** `Formato crudo/YYYY-MM-DD_consulta.md` (nuevo archivo)

---

#### FORMATEADOR

**Modelo:** ligero (Kimi / DeepSeek)  
**Activación:** manual — solo cuando el médico le indica explícitamente al Orquestador que desea formatear el Formato Crudo. Nunca se activa automáticamente.  
**Rol:** transformar el Formato Crudo en el Formato Médico siguiendo la plantilla del médico, en un flujo de dos pasos: borrador → confirmación → guardado definitivo.

**Comportamiento:**
1. Lee `Formato crudo/YYYY-MM-DD_consulta.md` de la consulta a formatear.
2. Puede leer archivos previos de `Formato médico/` como contexto (ej. alergias ya registradas) — nunca los modifica.
3. Genera un borrador del Formato Médico y avisa al Orquestador que está listo.
4. El Orquestador notifica al médico. El médico revisa el borrador.
5. Cuando el médico confirma, el Orquestador lo comunica al Formateador.
6. El Formateador guarda el archivo como definitivo e inmutable: `Formato médico/YYYY-MM-DD_consulta.md`.
7. Actualiza `index.md` del paciente con la nueva entrada.
8. Si un campo de la plantilla no tiene información en el Formato Crudo: dejarlo en blanco. Nunca inventar.

**Input:** `Formato crudo/YYYY-MM-DD_consulta.md` + plantilla del médico + archivos previos de `Formato médico/` (solo lectura)  
**Output:** borrador → (confirmación del médico) → `Formato médico/YYYY-MM-DD_consulta.md` definitivo + actualización de `index.md`

---

#### INVESTIGADOR

**Modelo:** ligero (Kimi / DeepSeek)  
**Activación:** por el Orquestador, cuando el médico hace una pregunta sobre consultas previas de un paciente.  
**Rol:** responder preguntas del médico en lenguaje natural, accediendo a los archivos de Formato Médico del paciente. La interacción ocurre en el mismo chat donde el médico habla con el Orquestador.

**Lógica de acceso a archivos:**

| Tipo de pregunta | Archivos que lee |
|-----------------|-----------------|
| Estado o situación actual del paciente | Archivos de Formato Médico más recientes |
| Evolución de un síntoma o condición en el tiempo | Todos los archivos de Formato Médico |
| Pregunta sobre una fecha o consulta específica | Ese archivo en concreto |
| El médico indica explícitamente qué consultas revisar | Respeta la indicación |

**Comportamiento adicional:**
- Al activarse, lee `index.md` del paciente para conocer todas las consultas disponibles.
- Responde siempre con referencias a consultas específicas (fecha + sección del expediente).
- Mantiene el contexto conversacional durante toda la sesión activa.
- No modifica ningún archivo en ningún caso.

**Input:** `index.md` del paciente + archivos de `Formato médico/` según la pregunta + preguntas del médico en chat  
**Output:** respuestas en lenguaje natural con referencias a consultas específicas

---

## 8. Flujos de trabajo

### Flujo A — Consulta nueva: paciente nuevo

```
ENTRADA detectada (voz / imagen / pdf) — paciente sin carpeta
            ↓
ORQUESTADOR detecta que no existe carpeta para el paciente
            → activa: CREADOR
            ↓
CREADOR inicializa estructura de carpetas
            → confirma al ORQUESTADOR
            ↓
ORQUESTADOR activa WHISPER o SCANNER según tipo de entrada
            ↓
WHISPER / SCANNER genera Formato Crudo
            → crea: Formato crudo/YYYY-MM-DD_consulta.md (inmutable)
            ↓
ORQUESTADOR notifica al médico — Formato Crudo disponible para revisión
ORQUESTADOR registra operación en log.md

            [El médico revisa el Formato Crudo]

MÉDICO le indica al ORQUESTADOR que formatee
            ↓
ORQUESTADOR activa FORMATEADOR
            ↓
FORMATEADOR lee Formato Crudo + plantilla + archivos previos de Formato médico/ (contexto)
            → genera: borrador del Formato Médico
            → avisa al ORQUESTADOR que el borrador está listo
            ↓
ORQUESTADOR avisa al médico — borrador disponible para revisión
            ↓
            [El médico revisa el borrador]

MÉDICO confirma
            ↓
FORMATEADOR guarda el archivo como definitivo e inmutable
            → crea: Formato médico/YYYY-MM-DD_consulta.md (inmutable)
            → actualiza: index.md del paciente
            ↓
ORQUESTADOR confirma al médico — Formato Médico guardado
ORQUESTADOR registra operación en log.md
```

---

### Flujo B — Consulta nueva: paciente existente

```
ENTRADA detectada (voz / imagen / pdf) — paciente con carpeta existente
            ↓
ORQUESTADOR confirma que la carpeta existe
            → activa WHISPER o SCANNER según tipo de entrada
            ↓
[continúa igual que Flujo A desde la generación del Formato Crudo]
```

---

### Flujo C — Médico consulta información de un paciente

```
MÉDICO le pregunta al ORQUESTADOR sobre un paciente
    (ej. "¿cuáles son sus medicamentos actuales?", "¿cómo ha evolucionado su presión?")
            ↓
ORQUESTADOR activa INVESTIGADOR con el paciente_id indicado
            ↓
INVESTIGADOR lee index.md del paciente
            → decide qué archivos de Formato médico/ leer según la pregunta
            ↓
INVESTIGADOR responde en el chat con referencias a consultas específicas
    (sesión activa mientras el médico siga consultando ese paciente)
            ↓
ORQUESTADOR registra operación en log.md
```

---

## 9. Plantilla del médico

El médico define su plantilla una sola vez. Vive en `medico/plantilla.md` y se referencia en `AGENTS.md`. El Formateador la replica exactamente en cada archivo de Formato Médico. Cualquier cambio a la plantilla aplica únicamente a partir de la siguiente consulta — los archivos anteriores conservan el formato con el que fueron generados.

Plantilla inicial de referencia:

```markdown
## Datos del Paciente
- Nombre completo:
- Fecha de nacimiento:
- Edad:
- Fecha de consulta:

## Antecedentes
- Heredofamiliares:
- Personales patológicos:
- Alergias:

## Consulta Actual
- Motivo de consulta:
- Síntomas referidos:
- Exploración física:
  - Tensión arterial:
  - Frecuencia cardíaca:
  - Temperatura:
  - Peso / Talla:

## Diagnóstico Clínico
- Diagnóstico principal:
- Diagnósticos secundarios:

## Plan de Tratamiento
- Indicaciones:

## Receta
| Medicamento | Dosis | Frecuencia | Duración |
|-------------|-------|------------|----------|
|             |       |            |          |

## Próxima Cita
- Fecha sugerida:
- Instrucciones al paciente:
```

---

## 10. AGENTS.md — schema del sistema

El archivo `AGENTS.md` vive en la raíz de `expedientes/` y es la fuente de verdad sobre cómo opera cada agente. Todos los agentes lo leen al inicializarse.

```markdown
# AGENTS.md — Expediente Vivo

## Estructura
- Cada paciente tiene su directorio en `expedientes/pacientes/{paciente_id}/`
- Formato Crudo: `Formato crudo/YYYY-MM-DD_consulta.md` — un archivo por consulta (Whisper o Scanner)
- Formato Médico: `Formato médico/YYYY-MM-DD_consulta.md` — un archivo por consulta (Formateador)
- Una vez creado un archivo de Formato Crudo o Formato Médico, es inmutable. Nunca se modifica.
- El Orquestador es el único que escribe en log.md — siempre en modo append

## Plantilla del médico
[Ver medico/plantilla.md — el Formateador la replica exactamente en cada Formato Médico]

## Reglas del Orquestador
1. Es el único punto de entrada para instrucciones del médico
2. Verificar si el paciente tiene carpeta antes de activar Whisper o Scanner; si no tiene, activar Creador primero
3. El Formateador solo se activa por instrucción explícita del médico — nunca automáticamente
4. El Investigador se activa cuando el médico hace una pregunta sobre consultas previas
5. Registrar en log.md el qué, dónde y por qué de cada operación delegada

## Reglas del Creador
1. Activarse solo cuando el Orquestador confirme que el paciente no tiene carpeta
2. Crear exactamente: index.md vacío, log.md vacío, carpeta Formato crudo/, carpeta Formato médico/
3. Confirmar al Orquestador una vez lista la estructura

## Reglas de Whisper
1. Crear nuevo archivo: Formato crudo/YYYY-MM-DD_consulta.md
2. Transcribir el audio de forma literal — sin filtrar ni interpretar
3. Nunca modificar archivos existentes en Formato crudo/

## Reglas del Scanner
1. Crear nuevo archivo: Formato crudo/YYYY-MM-DD_consulta.md
2. Para imágenes: describir y extraer todo el contenido visible de forma estructurada
3. Para PDFs: extraer y organizar todo el texto e información presente
4. No interpretar ni filtrar — solo extraer lo que hay
5. Nunca modificar archivos existentes en Formato crudo/

## Reglas del Formateador
1. Solo actuar cuando el Orquestador lo delegue por instrucción explícita del médico
2. Leer Formato crudo/YYYY-MM-DD_consulta.md de la consulta a formatear
3. Puede leer archivos previos de Formato médico/ como contexto — nunca modificarlos
4. Generar borrador del Formato Médico y avisar al Orquestador — no guardar aún
5. Guardar el archivo definitivo solo tras recibir confirmación del médico vía Orquestador
6. Campo sin información en el Formato Crudo → dejarlo en blanco. NUNCA inventar.
7. Actualizar index.md con la nueva entrada tras guardar el archivo definitivo
8. Nunca modificar archivos existentes en Formato médico/

## Reglas del Investigador
1. Al activarse, leer index.md del paciente indicado por el Orquestador
2. Decidir qué archivos de Formato médico/ leer según la pregunta:
   - Estado actual → archivos más recientes
   - Evolución en el tiempo → todos los archivos
   - Consulta específica → ese archivo en concreto
   - Indicación explícita del médico → respetar su indicación
3. Responder con referencias a consultas específicas (fecha + sección)
4. Mantener el contexto conversacional durante la sesión activa
5. No modificar ningún archivo

## Convenciones
- Nombres de archivo siempre: YYYY-MM-DD_consulta.md
- Frontmatter YAML obligatorio en cada archivo (paciente_id, medico_id, fecha_consulta, numero_consulta, tipo_entrada, agente_origen, tipo_documento)
- Un campo vacío se deja en blanco — nunca escribir "No especificado" ni inventar
- log.md es append-only — el Orquestador es el único que escribe en él
- index.md lo actualiza el Formateador cada vez que guarda un Formato Médico definitivo
```

---

## 11. Restricciones y decisiones de diseño

| Restricción | Decisión |
|------------|---------|
| Despliegue | 100% local para el MVP — sin dependencias cloud |
| Base de datos | Archivos markdown en filesystem — sin base vectorial en beta |
| Inmutabilidad | Formato Crudo y Formato Médico son inmutables una vez guardados |
| Activación del Formateador | Solo por instrucción explícita del médico — nunca automática |
| Plantilla del médico | Una sola plantilla por médico — aplica a todos sus pacientes |
| Orquestador | Único punto de entrada — el médico no interactúa directamente con ningún subagente |
| log.md | Uno por paciente — append-only — solo el Orquestador escribe en él |
| Modelos | Orquestador usa modelo pesado; subagentes usan modelos ligeros |

---

## 12. Decisiones pendientes

Las siguientes decisiones están fuera del scope de este PRD y se resolverán en fases posteriores del proyecto:

- Interfaz del dashboard donde el médico ve la lista de pacientes.
- Mecanismo concreto de captura de audio (micrófono integrado, app móvil, dispositivo externo).
- Autenticación y control de acceso por médico.
- Estructura de `paciente_id` y `medico_id` (generación, formato, unicidad).
- Política de retención y respaldo de archivos.
- Migración a ChromaDB cuando la beta supere los 500 pacientes.
