# CLAUDE.md — Cubicador AI (dgonzamat/Hack)

Principios de desarrollo y contexto técnico para sesiones de Claude Code.

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

**Restricciones absolutas (anti-alucinación):**
- Nunca inventar comportamiento de librerías (sklearn, openpyxl, PyMuPDF)
- Nunca asumir interfaces no documentadas de la API de Anthropic
- Nunca afirmar que tests pasaron si no se ejecutaron en esta sesión
- Si hay incertidumbre sobre una fórmula → citar norma MOP/EFE o preguntar

---

## Qué hace este proyecto

Extrae recintos e infraestructura desde planos PDF (via Claude API + PyMuPDF),
clasifica cada elemento con ML (TF-IDF + LogisticRegression) y genera
una cubicación con cantidades por partida + presupuesto en CLP.

**Foco principal:** proyectos viales/infraestructura chilena (calzadas, túneles,
puentes, alcantarillas, señalética, etc.). No es un cubicador arquitectónico genérico.

---

## Arquitectura de archivos

```
poc_cubicacion.py       # CLI principal — extrae recintos desde PDF via Claude API
cubicador.py            # Pipeline: clasificar_recinto() → cubicar() / cubicar_vial()
train_clasificador.py   # Entrena TF-IDF + LR → clasificador_recintos.pkl
presupuesto.py          # Cantidades × precios_cl.csv → subtotal + GG&U + IVA
excel.py                # Export openpyxl 4 hojas (Resumen/Recintos/Cubicación/Trazabilidad)
secciones_civiles.yaml  # Dimensiones por defecto por categoría vial (puente, túnel, etc.)
precios_cl.csv          # Precios indicativos Chile (ONDAC 2026Q1)
test_cubicador.py       # pytest — 187+ tests
```

---

## Clasificador ML

- **Modelo:** TF-IDF `FeatureUnion(char_wb(2,6) + word(1,2))` + `LogisticRegression(C=10)`
- **Dataset:** ~1217 ejemplos sintéticos — 680 vial (56%), resto húmedo/seco/exterior/común
- **Accuracy CV:** 94.0%
- **PKL:** `clasificador_recintos.pkl` (versionado en git, auto-actualizado por CI)
- **Umbral confianza:** `_CONFIANZA_ML_MIN = 0.60` — bajo este umbral → `fue_heuristica=True`
- **Active learning:** clasificaciones con proba < 0.75 se loguean en `_training_candidates.log`
  para revisión humana y posterior incorporación al dataset

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

**Regla crítica:** `_VIAL_OVERRIDE` intercepta términos viales antes del ML
para evitar clasificaciones erróneas en recintos arquitectónicos.

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

---

## ML — Reglas de experimentación

**Baseline obligatorio:** el modelo actual es 94.0% CV accuracy, 1217 ejemplos, 680 vial.
Nunca reportar mejora sin comparar contra este número con `make train-eval`.

**Antes de cambiar el dataset:**
1. Formular hipótesis explícita: *"agrego X ejemplos de categoría Y porque el modelo confunde Z"*
2. Verificar char n-gram overlap con el vocabulario vial — si hay overlap, el ejemplo causará regresión
3. Correr `make train-eval` antes y después — solo mergear si accuracy ≥ 94.0% o mejora medible

**Error analysis — proceso para atacar FP/FN:**
1. `python train_clasificador.py --eval` muestra confusion matrix
2. Identificar la categoría con más errores (hoy: comun→vial 15%, seco→vial 12%)
3. Inspeccionar ejemplos reales del `_training_candidates.log` para esa categoría
4. Agregar solo ejemplos de planos reales, no sintéticos

**Umbral de alerta:** si accuracy CV cae bajo 92% → no mergear, investigar causa raíz primero.

**Nunca:** experimentar sin hipótesis, decir que el modelo mejoró sin métricas, agregar
ejemplos sintéticos que compartan char n-grams con vial (causa regresión — PR #15).

---

## Lo que NO hacer

- No asumir área por defecto si `area_m2 is None` — omitir + listar en Trazabilidad
- No cubica áreas comunes por defecto (usar `--incluir-comunes` si se necesita)
- No commitear `_training_candidates.log` (está en .gitignore)
