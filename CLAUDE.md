# CLAUDE.md — Cubicador AI (dgonzamat/Hack)

Principios de desarrollo y contexto técnico para sesiones de Claude Code.

**IMPORTANTE:** Este repositorio es un *framework* reutilizable, no un proyecto
específico. Los datos de proyectos reales (JSONs con medidas, templates Excel del
mandante) viven fuera del repo. Nunca hardcodear paths de archivos del cliente.

---

## Principios de desarrollo (Karpathy)

**1. Pensar antes de codear**
Sacar supuestos y ambigüedades a la superficie antes de implementar.
Si hay incertidumbre, preguntar primero. No proceder en silencio.

**2. Mínimo código**
La solución más pequeña que resuelve el problema. Nada especulativo.
Sin abstracciones prematuras, sin manejo de errores para casos imposibles,
sin flexibilidad no solicitada.

**3. Cambios quirúrgicos**
Tocar solo lo necesario. Limpiar solo el propio desorden.
Respetar el estilo existente; no refactorizar código no relacionado.

**4. Ejecución orientada a objetivos**
Transformar tareas vagas en resultados medibles con pasos de verificación.
Ejecutar de forma independiente; las preguntas de clarificación van antes, no después.

---

## Reglas de trabajo

**Debugging — causa raíz, no síntomas:**
1. Reproducir el problema
2. Identificar la causa raíz
3. Explicar por qué ocurre
4. Implementar el fix mínimo confiable
5. Verificar regresiones con `make test`

Ejemplo: bug `_VIAL_CATS` — "REVESTIMIENTO TUNEL" matcheaba `\bTUNEL\b` antes que
`revestimiento_tunel`. Fix: reordenar la lista, no agregar lógica especial.

**Testing — verificación obligatoria:**
- Nunca reportar éxito sin ejecutar `make test`
- Nunca afirmar que el código compila sin verificarlo
- Verificar backward compatibility al modificar `clasificar_recinto` o `cubicar_vial`
- Si faltan tests para un cambio, proponer los mínimos de alto valor

**Seguridad:**
- `ANTHROPIC_API_KEY` → variable de entorno, nunca hardcodeado
- Nunca loguear contenido de PDFs (pueden tener datos de licitaciones confidenciales)
- `_training_candidates.log` excluido de git — puede contener datos de proyectos privados
- Nunca agregar paths de archivos del cliente al código fuente

**Restricciones absolutas (anti-alucinación):**
- Nunca inventar comportamiento de librerías (sklearn, openpyxl, PyMuPDF)
- Nunca asumir interfaces no documentadas de la API de Anthropic
- Nunca afirmar que tests pasaron si no se ejecutaron en esta sesión
- Si hay incertidumbre sobre una fórmula → citar norma MOP/EFE o preguntar

**Anti-patrones clave:**
- No asumir área por defecto si `area_m2 is None` — omitir + listar en Trazabilidad
- No cubica áreas comunes por defecto (usar `--incluir-comunes` si se necesita)
- No commitear `_training_candidates.log` (está en .gitignore)
- No hardcodear paths de templates del cliente en el código

---

## Qué hace este proyecto

Extrae recintos e infraestructura desde planos PDF (via Claude API + PyMuPDF),
clasifica cada elemento con ML (TF-IDF + LogisticRegression) y genera
una cubicación con cantidades por partida + presupuesto en CLP.

**Tres modos de uso:**
1. `--tipo arquitectonico` — recintos, puertas, ventanas, pintura, piso, cielo
2. `--tipo vial` — calzada, puente, túnel, alcantarilla, señalética, etc.
3. `--tipo electrico` — piques circulares + tramos de túnel liner para LAT subterránea

---

## Arquitectura de archivos

```
poc_cubicacion.py       # CLI principal — extrae recintos desde PDF via Claude API
cubicador.py            # Pipeline: clasificar_recinto() → cubicar() / cubicar_vial() / cubicar_electrico()
train_clasificador.py   # Entrena TF-IDF + LR → clasificador_recintos.pkl
presupuesto.py          # Cantidades × precios_cl.csv → subtotal + GG&U + IVA
excel.py                # Export arquitectónico — 4 hojas (Resumen/Recintos/Cubicación/Trazabilidad)
excel_licitacion.py     # Export formato licitación — rellena template .xlsx del mandante
secciones_civiles.yaml  # Dimensiones por defecto por categoría vial (puente, túnel, etc.)
precios_cl.csv          # Precios indicativos arquitectura Chile (ONDAC 2026Q1)
precios_electrico.csv   # Precios indicativos infraestructura eléctrica Chile (ONDAC 2026Q1)
ejemplo_recintos.json   # Ejemplo de JSON de entrada — proyecto arquitectónico
ejemplo_electrico.json  # Ejemplo de JSON de entrada — proyecto eléctrico (piques + tramos)
test_cubicador.py       # pytest — 187+ tests
```

---

## Modo eléctrico — cubicar_electrico()

Para proyectos de túnel liner con piques circulares (LAT subterránea, túneles de servicio):

```bash
python poc_cubicacion.py --from-json mi_proyecto.json \
    --tipo electrico \
    --template cuadro_precios_mandante.xlsx \
    --excel salida.xlsx
```

**Estructura del JSON de entrada** (`ejemplo_electrico.json` como referencia):
- `piques[]` — lista con `id`, `profundidad_m`, `km_aprox`, `notas`
- `tramos_tunel[]` — lista con `id`, `entre_piques`, `longitud_m`, `km_inicio`, `km_fin`
- El template `.xlsx` del mandante se pasa con `--template` (nunca hardcodeado)

**Constantes geométricas** (valores típicos para Ø4m/Ø2.21m):
- Pique: `AREA_PIQUE_M2 = π × r²` donde `r = diametro_pique_m / 2`
- Túnel: `AREA_TUNEL_M2 = π × r²` donde `r = diametro_tunel_m / 2`
- Radier: `RADIER_VOL_PER_M = diametro_tunel_m × espesor_radier_m`

**Mapeo ítems → Excel** (`excel_licitacion.py`):
- Piques: `4.{p}.1` excavación, `.2` retiro, `.3` liner, `.8` escalas, `.14`/`.15` brocal
- Túneles: `5.{t}.1` excavación, `.2` retiro, `.3` liner, `.7` radier
- Brocal definitivo: piques extremos → ítem N+1; intermedios → ítem N
  (depende del template del mandante — revisar sub-ítems antes de asumir)

---

## Clasificador ML y experimentación

- **Modelo:** TF-IDF `FeatureUnion(char_wb(2,6) + word(1,2))` + `LogisticRegression(C=10)`
- **Dataset:** ~1217 ejemplos sintéticos — 680 vial (56%), resto húmedo/seco/exterior/común
- **Accuracy CV baseline:** 94.0% — nunca reportar mejora sin comparar con `make train-eval`
- **PKL:** `clasificador_recintos.pkl` (versionado en git, auto-actualizado por CI)
- **Umbral confianza:** `_CONFIANZA_ML_MIN = 0.60` — bajo este umbral → `fue_heuristica=True`
- **Active learning:** clasificaciones con proba < 0.75 se loguean en `_training_candidates.log`

**Flujo de mejora continua:**
```
plano PDF → cubicador.py → _training_candidates.log
                                  ↓ (revisión humana)
                        train_clasificador.py (nuevo ejemplo)
                                  ↓ (push a master)
                        GitHub Actions reentrenamiento
                                  ↓
                        clasificador_recintos.pkl actualizado
```

**Antes de cambiar el dataset:**
1. Formular hipótesis: *"agrego X ejemplos de categoría Y porque el modelo confunde Z"*
2. Verificar char n-gram overlap: `python -c "from train_clasificador import _norm; print(_norm('TU EJEMPLO'))"` y buscar substrings en el vocabulario vial — si hay overlap de 4+ chars, causará regresión
3. Correr `make train-eval` antes y después — mergear solo si accuracy no retrocede (≥ 94.0%) o hay mejora > 0.2pp

**Error analysis — proceso para atacar FP/FN:**
1. `python train_clasificador.py --eval` imprime confusion matrix por categoría
2. Identificar la categoría con mayor % error total
3. Inspeccionar ejemplos reales de esa categoría en `_training_candidates.log`
4. Agregar solo ejemplos de planos reales, no sintéticos

**Umbral de alerta:** accuracy CV < 92% → no mergear, investigar causa raíz.

---

## Categorías viales clave (`_VIAL_CATS` en cubicador.py)

El orden importa — específicos antes que genéricos:

| Categoría | Fórmula principal |
|---|---|
| `calzada` | área × espesor capas (base + carpeta asfáltica) |
| `vereda` | área × espesor hormigón |
| `puente` | vol tablero × H30 + acero + moldaje + neoprenos + juntas |
| `tunel` | área × excavación + sostenimiento + impermeabilización |
| `revestimiento_tunel` | área directa (shotcrete o HF definitivo) |
| `cuneta` | longitud × sección hormigón |
| `alcantarilla` | longitud × tipo (cajón/circular/metálica) |
| `señalizacion` | conteo unidades |

**Regla crítica:** `_VIAL_OVERRIDE` intercepta términos viales antes del ML.

---

## Comandos frecuentes

```bash
make train          # reentrena + guarda pkl
make train-eval     # accuracy CV sin guardar pkl
make train-tune     # GridSearchCV (lento ~5min)
make test           # pytest test_cubicador.py -q
make lint           # ruff + codespell
make all            # train + test + lint
```

---

## Normativa de referencia (Chile)

- Manual de Carreteras MOP Vol.3 (terraplenes/cortes), Vol.5 (puentes), Vol.8 (túneles)
- EFE Norma Vía 2019 (ferroviario)
- MINVU Vialidad Ciclo-Inclusiva 2025 (ciclovías)
- Manual Señalización MOP 2012
- ONDAC 2026Q1 (precios unitarios)

---

## CI/CD

- **GitHub Actions** (`.github/workflows/train_model.yml`): reentrenamiento automático
  al hacer push de cambios en `train_clasificador.py` o cada domingo 3am UTC.
- **GitGuardian**: check de secretos en cada PR.
- **ruff**: solo archivos `.py` — `pyproject.toml` excluye `.json`/`.yaml`/`.csv`.
