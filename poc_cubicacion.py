#!/usr/bin/env python3
"""
PoC: Cubicación AI con Claude Vision — v4
Uso: python poc_cubicacion.py plano.pdf
     python poc_cubicacion.py plano.pdf --paginas 1,2,3
     python poc_cubicacion.py plano.pdf --tiles 2x2
     python poc_cubicacion.py plano.pdf --tiles 1x1  (sin tiling)
"""

import argparse
import base64
import io
import json
import os
import re
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path

import anthropic
import pymupdf
from PIL import Image

# ─── Configuración ────────────────────────────────────────────────────────────

MODELO = "claude-opus-4-7"
DPI_DEFAULT = 180
DPI_PREPASS = 72       # resolución mínima para pre-pass (solo leer tabla de áreas)
MAX_TOKENS = 4096
TILE_MAX_PX = 2800
AUTO_TILE_THRESH = 3500
TILE_OVERLAP = 0.12
FUZZY_THRESHOLD = 0.80  # similitud mínima para considerar mismo recinto

POSICIONES = {
    (0, 0): "CUADRANTE SUPERIOR IZQUIERDO (zona NW del plano)",
    (0, 1): "CUADRANTE SUPERIOR DERECHO (zona NE del plano)",
    (1, 0): "CUADRANTE INFERIOR IZQUIERDO (zona SW del plano)",
    (1, 1): "CUADRANTE INFERIOR DERECHO (zona SE del plano)",
    (-1, -1): "CENTRO DEL PLANO (zona central, intersección de cuadrantes)",
}

# ─── Prompts ──────────────────────────────────────────────────────────────────

PROMPT_SCHEDULE = """
Analiza este plano arquitectónico y busca la tabla de áreas o cuadro de superficies.
Si existe, extrae TODAS las filas incluyendo recintos individuales (no solo totales).

Devuelve ÚNICAMENTE JSON válido (sin texto adicional):
{
  "tiene_tabla": true,
  "departamentos": [
    {
      "id": "DEPTO A1",
      "recintos": [
        {"nombre": "DORMITORIO PRINCIPAL", "area_m2": 12.5},
        {"nombre": "LIVING COMEDOR", "area_m2": 28.4}
      ],
      "area_total_m2": 85.2
    }
  ],
  "nota": "descripción de dónde está la tabla o por qué no hay"
}

IMPORTANTE: lista cada recinto individual si la tabla los detalla.
Si la tabla solo muestra totales por departamento, lista esos totales con nombre "AREA PISO" u otro nombre genérico visible.
Si NO hay tabla de áreas, devuelve: {"tiene_tabla": false, "departamentos": [], "nota": "..."}
"""


def prompt_buscar_deptos(ids_faltantes: list[str], schedule_ctx: str) -> str:
    ids = ", ".join(ids_faltantes)
    return f"""Eres un cubicador profesional. Analiza este plano arquitectónico completo.

La tabla de áreas indica que existen los siguientes departamentos que AÚN NO han sido detectados:
{ids}

TABLA DE REFERENCIA:
{schedule_ctx}

Busca en TODO el plano etiquetas, rótulos o textos que identifiquen estos departamentos.
Extrae los recintos de SOLO esos departamentos faltantes.

Devuelve ÚNICAMENTE JSON válido:
{{
  "recintos": [
    {{
      "nombre": "DORMITORIO PRINCIPAL",
      "departamento": "DEPTO A1",
      "area_m2": 12.5,
      "confianza": 0.85,
      "nota": "encontrado en zona NW del plano"
    }}
  ],
  "nota": "descripción de lo que encontraste o no encontraste"
}}

Si no encuentras ninguno, devuelve: {{"recintos": [], "nota": "no visibles en este plano"}}
"""


def prompt_tile(posicion: str | None, schedule_ctx: str) -> str:
    pos_txt = f"\nEstás analizando el {posicion} del plano.\n" if posicion else ""
    sched_txt = f"\nTABLA DE ÁREAS DE REFERENCIA (usa estos nombres exactos):\n{schedule_ctx}\n" if schedule_ctx else ""
    return f"""Eres un cubicador profesional experto en arquitectura LATAM.
{pos_txt}{sched_txt}
Extrae TODOS los recintos visibles en esta imagen (incluyendo los parcialmente cortados en los bordes).

REGLA CRÍTICA DE NOMBRES: usa el nombre exacto que aparece en la etiqueta del recinto.
NO agregues calificadores como "(parcial)", "(centro)", "(depto derecho)", etc.
DEPARTAMENTO: usa SOLO el código oficial visible (ej: "A1", "B2", "DEPTO B1") — NO inventes ni describas ubicación.
Si no puedes identificar el departamento al que pertenece, deja el campo "departamento" como null.

Devuelve ÚNICAMENTE JSON válido:
{{
  "lamina": {{
    "titulo": "nombre si es visible, si no null",
    "escala": "ej: 1:75 si es visible, si no null",
    "tipo": "planta | elevacion | corte | detalle | desconocido"
  }},
  "recintos": [
    {{
      "nombre": "DORMITORIO PRINCIPAL",
      "departamento": "DEPTO B1",
      "area_m2": 11.2,
      "dimensiones_estimadas": {{"largo_m": 4.0, "ancho_m": 2.8}},
      "confianza": 0.95,
      "nota": "leída de etiqueta / estimada"
    }}
  ],
  "muros": {{
    "exterior_ml": null,
    "interior_ml": null,
    "confianza": 0.0,
    "nota": ""
  }},
  "vanos": {{
    "puertas": [{{"tipo": "simple 90cm", "cantidad": 3}}],
    "ventanas": [{{"tipo": "corredera 120x100", "cantidad": 2}}]
  }},
  "observaciones": "limitaciones encontradas en este cuadrante",
  "calidad_plano": "alta | media | baja",
  "tiene_cotas": true,
  "tiene_escala_grafica": false
}}

Reglas:
- confianza 0.9+ = etiqueta explícita o tabla de áreas | 0.6-0.8 = estimado | <0.5 = muy incierto
- Usa null si no puedes determinar — NUNCA inventes
- Incluye recintos cortados en el borde con confianza reducida
- dimensiones_estimadas es OPCIONAL: incluyelo solo si puedes leer cotas o estimar largo/ancho con confianza ≥ 0.6
"""


# ─── Renderizado ──────────────────────────────────────────────────────────────

def render_pagina(ruta: Path, num_pag: int, dpi: int) -> pymupdf.Pixmap:
    doc = pymupdf.open(str(ruta))
    pix = doc[num_pag].get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), alpha=False)
    doc.close()
    return pix


def pix_to_pil(pix: pymupdf.Pixmap) -> Image.Image:
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def img_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.standard_b64encode(buf.getvalue()).decode()


def escalar_img(img: Image.Image, max_px: int) -> Image.Image:
    W, H = img.size
    if max(W, H) <= max_px:
        return img
    factor = max_px / max(W, H)
    return img.resize((int(W * factor), int(H * factor)), Image.LANCZOS)


def generar_tiles(img: Image.Image, nx: int, ny: int, overlap: float, add_center: bool = False) -> list[dict]:
    W, H = img.size
    tw, th = W / nx, H / ny
    pad_x, pad_y = int(tw * overlap), int(th * overlap)
    tiles = []
    for row in range(ny):
        for col in range(nx):
            x0 = max(0, int(col * tw) - pad_x)
            y0 = max(0, int(row * th) - pad_y)
            x1 = min(W, int((col + 1) * tw) + pad_x)
            y1 = min(H, int((row + 1) * th) + pad_y)
            crop = img.crop((x0, y0, x1, y1))
            crop = escalar_img(crop, TILE_MAX_PX)
            tiles.append({
                "b64": img_to_b64(crop),
                "row": row, "col": col,
                "posicion": POSICIONES.get((row, col), f"SECCIÓN {row+1},{col+1}"),
                "size": crop.size,
            })
    if add_center and nx == 2 and ny == 2:
        cx, cy = W // 2, H // 2
        hw = min(TILE_MAX_PX, W // 2)
        hh = min(TILE_MAX_PX, H // 2)
        x0 = max(0, cx - hw // 2)
        y0 = max(0, cy - hh // 2)
        x1 = min(W, cx + hw // 2)
        y1 = min(H, cy + hh // 2)
        crop = img.crop((x0, y0, x1, y1))
        crop = escalar_img(crop, TILE_MAX_PX)
        tiles.append({
            "b64": img_to_b64(crop),
            "row": -1, "col": -1,
            "posicion": POSICIONES[(-1, -1)],
            "size": crop.size,
        })
    return tiles


# ─── Claude ───────────────────────────────────────────────────────────────────

def llamar_claude(client: anthropic.Anthropic, b64: str, prompt: str, max_reintentos: int = 3) -> tuple[dict, int, int]:
    _retryable = (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError)
    for intento in range(max_reintentos):
        try:
            resp = client.messages.create(
                model=MODELO, max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": prompt},
                ]}],
            )
            break
        except _retryable as e:
            if intento == max_reintentos - 1:
                raise
            espera = 2 ** (intento + 1)
            print(f" [reintento {intento+1}/{max_reintentos-1} en {espera}s — {type(e).__name__}]", end="", flush=True)
            time.sleep(espera)
    texto = resp.content[0].text.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    texto = texto.strip()
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        datos = {"error": "JSON inválido", "raw": texto[:400]}
    return datos, resp.usage.input_tokens, resp.usage.output_tokens


# ─── Merge ────────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Normaliza nombre: mayúsculas, sin guiones/barras, sin espacios extra.
    Preserva puntos (necesario para 'DORM.PRINCIPAL').
    """
    return re.sub(r"\s+", " ", s.upper().replace("-", " ").replace("/", " ")).strip()


def _depto_match(sched_id: str, ids_encontrados: set[str]) -> bool:
    """True si sched_id está cubierto por alguno de los ids extraídos.
    Maneja casos como 'B1' en schedule vs 'DEPTO B1' en extracción.
    """
    sn = _norm(sched_id)
    for ei in ids_encontrados:
        if sn == ei or sn in ei or ei in sn:
            return True
    return False


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _clave_recinto(rec: dict, nombre_only: bool = False) -> str:
    nombre = _norm(rec.get("nombre", ""))
    if nombre_only:
        return nombre
    depto = _norm(rec.get("departamento", "") or "")
    return f"{depto}|{nombre}" if depto else nombre


def _recintos_misma_unidad(a: dict, b: dict) -> bool:
    """True si a y b representan el mismo recinto físico."""
    clave_a = _clave_recinto(a)
    clave_b = _clave_recinto(b)
    if _sim(clave_a, clave_b) >= FUZZY_THRESHOLD:
        return True
    # Cross-match: si uno tiene departamento y el otro no, comparar solo por nombre
    a_tiene = bool(a.get("departamento"))
    b_tiene = bool(b.get("departamento"))
    if a_tiene != b_tiene:
        return _sim(_clave_recinto(a, nombre_only=True), _clave_recinto(b, nombre_only=True)) >= FUZZY_THRESHOLD
    return False


def merge_recintos(todos: list[dict]) -> list[dict]:
    """
    Agrupa recintos por (departamento, nombre) con fuzzy matching.
    De cada grupo conserva el de mayor confianza que tenga área.
    Si un recinto sin departamento coincide con uno que sí tiene, se prefiere el asignado.
    """
    def _clave_sort(r: dict) -> tuple:
        return (1 if r.get("departamento") else 0, 1 if r.get("area_m2") is not None else 0, r.get("confianza") or 0)

    grupos: list[list[dict]] = []

    for rec in todos:
        colocado = False
        for grupo in grupos:
            # Comparar contra el miembro de mayor confianza del grupo, no el primero
            representante = max(grupo, key=_clave_sort)
            if _recintos_misma_unidad(rec, representante):
                grupo.append(rec)
                colocado = True
                break
        if not colocado:
            grupos.append([rec])

    resultado = []
    for grupo in grupos:
        mejor = dict(sorted(grupo, key=_clave_sort, reverse=True)[0])

        # Área ponderada: promedio pesado por confianza de todos los miembros con área
        areas_conf = [(r["area_m2"], r.get("confianza") or 0) for r in grupo if r.get("area_m2") is not None]
        if len(areas_conf) > 1:
            peso_total = sum(c for _, c in areas_conf)
            if peso_total > 0:
                mejor["area_m2"] = round(sum(a * c for a, c in areas_conf) / peso_total, 1)
            # Si los tiles coinciden en área (Δ < 10%), aumentar confianza ligeramente
            vals = [a for a, _ in areas_conf]
            spread = max(vals) - min(vals)
            if (sum(vals) / len(vals)) > 0 and spread / (sum(vals) / len(vals)) < 0.10:
                mejor["confianza"] = round(min(0.99, (mejor.get("confianza") or 0) + 0.05), 2)

        resultado.append(mejor)

    return sorted(resultado, key=lambda r: (_norm(r.get("departamento") or ""), _norm(r.get("nombre", ""))))


def merge_tiles(tile_results: list[dict], num_pag: int) -> dict:
    tokens_in = tokens_out = 0
    lamina_info = {"titulo": None, "escala": None, "tipo": "desconocido"}
    tiene_cotas = False
    escala_grafica = False
    calidades = []
    observaciones = []

    todos_recintos: list[dict] = []
    ext_ml = int_ml = 0.0
    puertas_map: dict[str, int] = {}
    ventanas_map: dict[str, int] = {}
    n_tiles_ok = 0

    for t in tile_results:
        if "error" in t:
            continue
        n_tiles_ok += 1
        tokens_in += t.get("_tokens_entrada", 0)
        tokens_out += t.get("_tokens_salida", 0)

        lam = t.get("lamina", {})
        if not lamina_info["titulo"] and lam.get("titulo"):
            lamina_info["titulo"] = lam["titulo"]
        if not lamina_info["escala"] and lam.get("escala"):
            lamina_info["escala"] = lam["escala"]
        if lam.get("tipo", "desconocido") != "desconocido":
            lamina_info["tipo"] = lam["tipo"]
        if t.get("tiene_cotas"):
            tiene_cotas = True
        if t.get("tiene_escala_grafica"):
            escala_grafica = True
        if t.get("calidad_plano"):
            calidades.append(t["calidad_plano"])
        obs = t.get("observaciones", "")
        pos = t.get("_posicion", "")
        if obs:
            observaciones.append(f"[{pos}] {obs}" if pos else obs)

        todos_recintos.extend(t.get("recintos", []))

        m = t.get("muros", {})
        ext_ml += m.get("exterior_ml") or 0
        int_ml += m.get("interior_ml") or 0

        v = t.get("vanos", {})
        for p in v.get("puertas", []):
            tipo = p.get("tipo", "—")
            puertas_map[tipo] = puertas_map.get(tipo, 0) + p.get("cantidad", 0)
        for w in v.get("ventanas", []):
            tipo = w.get("tipo", "—")
            ventanas_map[tipo] = ventanas_map.get(tipo, 0) + w.get("cantidad", 0)

    recintos_merged = merge_recintos(todos_recintos)

    # Corregir solapamiento: vanos y muros acumulados desde tiles individuales
    if n_tiles_ok > 1:
        disc = 1 - TILE_OVERLAP
        puertas_map = {k: max(1, round(v * disc)) for k, v in puertas_map.items()}
        ventanas_map = {k: max(1, round(v * disc)) for k, v in ventanas_map.items()}
        # Muros: cada segmento aparece en ~2 tiles (exterior) o más (interior).
        # Factor conservador: dividir por 2 como mejor estimación.
        ext_ml = ext_ml / 2 if ext_ml else ext_ml
        int_ml = int_ml / 2 if int_ml else int_ml

    calidad = "alta" if "alta" in calidades else ("media" if "media" in calidades else "baja")

    return {
        "_pagina": num_pag + 1,
        "_tiles_procesados": n_tiles_ok,
        "_tokens_entrada": tokens_in,
        "_tokens_salida": tokens_out,
        "lamina": lamina_info,
        "recintos": recintos_merged,
        "muros": {
            "exterior_ml": round(ext_ml, 1) if ext_ml else None,
            "interior_ml": round(int_ml, 1) if int_ml else None,
            "confianza": 0.6,
            "nota": "estimado sumando tiles",
        },
        "vanos": {
            "puertas": [{"tipo": k, "cantidad": v} for k, v in puertas_map.items()],
            "ventanas": [{"tipo": k, "cantidad": v} for k, v in ventanas_map.items()],
        },
        "losas": {"area_m2": None, "confianza": 0.0, "nota": ""},
        "observaciones": " | ".join(observaciones),
        "calidad_plano": calidad,
        "tiene_cotas": tiene_cotas,
        "tiene_escala_grafica": escala_grafica,
    }


# ─── Output ───────────────────────────────────────────────────────────────────

def calcular_costo(ti: int, to: int) -> float:
    return (ti * 15 + to * 75) / 1_000_000


def imprimir_resumen(resultados: list[dict], schedules: dict) -> None:
    print("\n" + "═" * 66)
    print("  RESUMEN DE CUBICACIÓN")
    print("═" * 66)

    total_area = total_puertas = total_ventanas = 0
    total_costo = 0.0
    lams_ok = 0

    for r in resultados:
        pag = r.get("_pagina", "?")
        if "error" in r:
            print(f"\n  ✗ Lámina {pag}: {r.get('error','error')}")
            continue
        lams_ok += 1

        lam = r.get("lamina", {})
        titulo = lam.get("titulo") or "sin título"
        tipo = lam.get("tipo", "?")
        escala = lam.get("escala") or "no detectada"
        calidad = r.get("calidad_plano", "?")
        cotas = "✓" if r.get("tiene_cotas") else "✗"
        n_tiles = r.get("_tiles_procesados", 1)
        modo = f"tiles×{n_tiles}" if n_tiles > 1 else "imagen completa"
        costo = calcular_costo(r.get("_tokens_entrada", 0), r.get("_tokens_salida", 0))
        total_costo += costo

        print(f"\n  ── Lámina {pag}: {titulo} ({tipo}) [{modo}] ──")
        print(f"     Escala: {escala}  |  Calidad: {calidad}  |  Cotas: {cotas}")

        recintos = r.get("recintos", [])
        con_area = [x for x in recintos if x.get("area_m2") is not None]
        sin_area = [x for x in recintos if x.get("area_m2") is None]
        area_pag = sum(x["area_m2"] for x in con_area)
        total_area += area_pag

        print(f"     Recintos: {len(con_area)} con área  +  {len(sin_area)} sin área  =  {area_pag:.1f} m² total")

        # Agrupar por departamento para mostrar
        deptos: dict[str, list] = {}
        for rec in recintos:
            d = rec.get("departamento") or "─ SIN ASIGNAR"
            deptos.setdefault(d, []).append(rec)

        for depto, recs in sorted(deptos.items()):
            print(f"       {depto}:")
            for rec in recs:
                area = rec.get("area_m2")
                conf = rec.get("confianza") or 0
                area_str = f"{area:.1f} m²" if area else "sin área"
                flag = "✓" if conf >= 0.70 else "⚠"
                print(f"         {flag} {rec['nombre']}: {area_str}  ({conf:.0%})")

        # Comparar con schedule si existe — por departamento cuando sea posible
        sched = schedules.get(pag)
        if sched and sched.get("tiene_tabla"):
            sched_deptos = {
                _norm(d.get("id", "")): d
                for d in sched.get("departamentos", [])
                if d.get("id")
            }
            # Suma extraída por departamento
            extraido_por_depto: dict[str, float] = {}
            for rec in recintos:
                dep_norm = _norm(rec.get("departamento") or "SIN ASIGNAR")
                if rec.get("area_m2") is not None:
                    extraido_por_depto[dep_norm] = extraido_por_depto.get(dep_norm, 0) + rec["area_m2"]

            print()
            alguna_fila = False
            for dep_norm, dep_data in sorted(sched_deptos.items()):
                sched_dep_total = dep_data.get("area_total_m2") or 0
                # Match extraído contra schedule_id con tolerancia (B1 ↔ DEPTO B1)
                ext_dep = 0.0
                for ext_key, ext_val in extraido_por_depto.items():
                    if _depto_match(dep_norm, {ext_key}) or _depto_match(ext_key, {dep_norm}):
                        ext_dep += ext_val
                if sched_dep_total > 0:
                    alguna_fila = True
                    if ext_dep > 0:
                        pct = abs(ext_dep - sched_dep_total) / sched_dep_total * 100
                        flag = "✓" if pct <= 15 else "⚠"
                        print(f"     {flag} {dep_data['id']}: sched {sched_dep_total:.1f} m²  extraído {ext_dep:.1f} m²  Δ {pct:.1f}%")
                    else:
                        print(f"     ✗ {dep_data['id']}: sched {sched_dep_total:.1f} m²  —  NO DETECTADO")

            # Total global
            sched_total = sum(d.get("area_total_m2") or 0 for d in sched.get("departamentos", []))
            if alguna_fila and sched_total > 0:
                pct_global = abs(area_pag - sched_total) / sched_total * 100
                flag_g = "✓" if pct_global <= 15 else "⚠"
                print(f"     {flag_g} TOTAL: sched {sched_total:.1f} m²  extraído {area_pag:.1f} m²  Δ {pct_global:.1f}%")

        m = r.get("muros", {})
        if m.get("exterior_ml") or m.get("interior_ml"):
            ext = f"{m['exterior_ml']:.1f} ml" if m.get("exterior_ml") else "?"
            inte = f"{m['interior_ml']:.1f} ml" if m.get("interior_ml") else "?"
            print(f"     Muros: exterior {ext}  |  interior {inte}")

        v = r.get("vanos", {})
        np_ = sum(p.get("cantidad", 0) for p in v.get("puertas", []))
        nv_ = sum(w.get("cantidad", 0) for w in v.get("ventanas", []))
        total_puertas += np_
        total_ventanas += nv_

        obs = r.get("observaciones", "")
        if obs:
            for line in obs.split(" | "):
                line = line.strip()
                if line:
                    print(f"     ⚑ {line[:115]}")

        print(f"     Costo API: ${costo:.4f} USD")

    print("\n" + "─" * 66)
    print("  TOTALES")
    print("─" * 66)
    print(f"  Láminas:             {lams_ok}")
    print(f"  Área total:          {total_area:.1f} m²")
    print(f"  Puertas detectadas:  {total_puertas} un")
    print(f"  Ventanas detectadas: {total_ventanas} un")
    print(f"  Costo total API:     ${total_costo:.4f} USD")
    print("═" * 66)
    if total_area > 0:
        print(f"\n  · Recintos ⚠ (confianza < 70%) = revisar manualmente")
        print(f"  · Δ < 15% vs tabla de áreas = precisión aceptable para presupuesto")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────

def _make_client() -> anthropic.Anthropic:
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    token_file = os.environ.get("CLAUDE_SESSION_INGRESS_TOKEN_FILE")
    if base_url and token_file and not os.environ.get("ANTHROPIC_API_KEY"):
        token = Path(token_file).read_text().strip()
        return anthropic.Anthropic(auth_token=token, base_url=base_url)
    return anthropic.Anthropic()


def _parse_tiles(valor: str) -> tuple[int, int]:
    partes = valor.lower().split("x")
    if len(partes) == 2:
        return int(partes[0]), int(partes[1])
    raise argparse.ArgumentTypeError(f"Formato inválido: '{valor}'. Usa NxM, ej: 2x2")


def procesar_pagina(
    client: anthropic.Anthropic,
    ruta: Path,
    idx: int,
    total: int,
    dpi: int,
    tiles_forzado: tuple[int, int] | None,
) -> tuple[dict, dict]:
    """Procesa una página. Retorna (resultado_cubicacion, schedule_dict)."""
    print(f"  Lámina {idx+1}/{total}:")
    t0 = time.time()

    pix = render_pagina(ruta, idx, dpi)
    img = pix_to_pil(pix)
    W, H = img.size
    print(f"    Renderizado: {W}×{H}px @ {dpi}DPI")

    # Pre-pass: extraer tabla de áreas a baja resolución
    print(f"    Pre-pass (tabla de áreas)...", end=" ", flush=True)
    t1 = time.time()
    img_low = escalar_img(img, 1400)
    sched_datos, ti, to = llamar_claude(client, img_to_b64(img_low), PROMPT_SCHEDULE)
    sched_costo = calcular_costo(ti, to)
    tiene_tabla = sched_datos.get("tiene_tabla", False)
    n_deptos = len(sched_datos.get("departamentos", []))
    print(f"{'tabla ✓ (' + str(n_deptos) + ' deptos)' if tiene_tabla else 'sin tabla'}  ({time.time()-t1:.1f}s, ${sched_costo:.4f})")

    # Construir contexto de schedule para prompt de tiles
    schedule_ctx = ""
    if tiene_tabla and sched_datos.get("departamentos"):
        deptos_lista = sched_datos["departamentos"]
        ids_canonicos = [d.get("id", "") for d in deptos_lista if d.get("id")]
        lineas = [
            f"IDs OFICIALES — usa EXACTAMENTE estos (sin 'DEPTO', sin prefijos): {', '.join(ids_canonicos)}",
            "",
        ]
        for dep in deptos_lista:
            did = dep.get("id", "?")
            total_dep = dep.get("area_total_m2", "?")
            lineas.append(f"  {did} (total {total_dep} m²):")
            for rec in dep.get("recintos", []):
                lineas.append(f"    - {rec['nombre']}: {rec.get('area_m2', '?')} m²")
        schedule_ctx = "\n".join(lineas)

    # Decidir grid
    auto_tile = False
    if tiles_forzado:
        nx, ny = tiles_forzado
    elif W > AUTO_TILE_THRESH:
        nx, ny = 2, 2
        auto_tile = True
        print(f"    Auto-tiling 2×2 + centro (imagen > {AUTO_TILE_THRESH}px)")
    else:
        nx, ny = 1, 1

    # Procesar tiles
    if nx == 1 and ny == 1:
        img_s = escalar_img(img, TILE_MAX_PX)
        print(f"    → imagen completa ({img_s.size[0]}×{img_s.size[1]}px)...", end=" ", flush=True)
        datos, ti2, to2 = llamar_claude(client, img_to_b64(img_s), prompt_tile(None, schedule_ctx))
        datos.update({"_pagina": idx+1, "_posicion": None, "_tokens_entrada": ti+ti2, "_tokens_salida": to+to2})
        costo = calcular_costo(ti+ti2, to+to2)
        print(f"OK ({time.time()-t0:.1f}s, {len(datos.get('recintos',[]))} recintos, ${costo:.4f})")
        return datos, sched_datos

    tiles = generar_tiles(img, nx, ny, TILE_OVERLAP, add_center=auto_tile)
    tile_results = []
    total_ti = ti
    total_to = to

    for tile in tiles:
        pos = tile["posicion"]
        sz = tile["size"]
        print(f"    → {pos.split('(')[0].strip()} ({sz[0]}×{sz[1]}px)...", end=" ", flush=True)
        t1 = time.time()
        try:
            res, ti2, to2 = llamar_claude(client, tile["b64"], prompt_tile(pos, schedule_ctx))
            total_ti += ti2
            total_to += to2
            res.update({"_pagina": idx+1, "_posicion": pos, "_tokens_entrada": ti2, "_tokens_salida": to2})
            n_rec = len(res.get("recintos", []))
            c = calcular_costo(ti2, to2)
            print(f"OK ({time.time()-t1:.1f}s, {n_rec} recintos, ${c:.4f})")
            tile_results.append(res)
        except Exception as e:
            print(f"ERROR: {e}")
            tile_results.append({"error": str(e), "_pagina": idx+1, "_posicion": pos})

    merged = merge_tiles(tile_results, idx)

    # Re-pass dirigido para departamentos faltantes del schedule
    if tiene_tabla and schedule_ctx:
        ids_encontrados = {
            _norm(r.get("departamento") or "") for r in merged.get("recintos", []) if r.get("departamento")
        }
        ids_faltantes = [
            d.get("id", "") for d in sched_datos.get("departamentos", [])
            if d.get("id") and not _depto_match(d.get("id", ""), ids_encontrados)
        ]
        if ids_faltantes:
            print(f"    Re-pass deptos faltantes {ids_faltantes}...", end=" ", flush=True)
            t1 = time.time()
            try:
                img_low = escalar_img(img, 1400)
                res_rp, ti_rp, to_rp = llamar_claude(
                    client, img_to_b64(img_low),
                    prompt_buscar_deptos(ids_faltantes, schedule_ctx),
                )
                total_ti += ti_rp
                total_to += to_rp
                nuevos = res_rp.get("recintos", [])
                c_rp = calcular_costo(ti_rp, to_rp)
                print(f"OK ({time.time()-t1:.1f}s, {len(nuevos)} recintos nuevos, ${c_rp:.4f})")
                if nuevos:
                    todos_rec = merged.get("recintos", []) + nuevos
                    merged["recintos"] = merge_recintos(todos_rec)
            except Exception as e:
                print(f"ERROR: {e}")

    merged["_tokens_entrada"] = total_ti
    merged["_tokens_salida"] = total_to
    n_rec = len(merged.get("recintos", []))
    n_area = len([r for r in merged.get("recintos", []) if r.get("area_m2") is not None])
    print(f"    Merge → {n_rec} recintos únicos ({n_area} con área)  total {time.time()-t0:.1f}s")

    return merged, sched_datos


def main() -> None:
    parser = argparse.ArgumentParser(description="PoC cubicación AI v5 — cubicación + presupuesto + Excel")
    parser.add_argument("pdf", nargs="?", default=None,
                        help="PDF del plano. Omitir si se usa --from-json.")
    parser.add_argument("--from-json", default=None, metavar="PATH",
                        help="Carga recintos desde JSON pre-extraído (omite API). "
                             "Formato: {\"resultados\":[...], \"schedules\":{...}}")
    parser.add_argument("--paginas", default=None)
    parser.add_argument("--dpi", type=int, default=DPI_DEFAULT)
    parser.add_argument("--tiles", type=_parse_tiles, default=None,
                        help="Grid ej: 2x2. Auto si no se especifica.")
    parser.add_argument("--json", default=None)
    parser.add_argument("--excel", default=None, help="Ruta de salida Excel con cubicación + presupuesto")
    parser.add_argument("--precios", default="precios_cl.csv",
                        help="CSV de precios unitarios (default precios_cl.csv)")
    parser.add_argument("--altura", type=float, default=2.4,
                        help="Altura piso-cielo global en metros (default 2.4)")
    parser.add_argument("--alturas", default=None,
                        help='Overrides JSON por keyword. Ej: \'{"BAÑO":2.2,"DORM":2.4}\'')
    parser.add_argument("--gg-utilidad", type=float, default=0.25,
                        help="Fracción de GG + Utilidad (default 0.25)")
    parser.add_argument("--iva", type=float, default=0.19,
                        help="Fracción IVA (default 0.19 Chile)")
    parser.add_argument("--incluir-comunes", action="store_true",
                        help="Incluye áreas comunes en cubicación (default false)")
    parser.add_argument("--tipo", default="arquitectonico",
                        choices=["arquitectonico", "vial", "electrico"],
                        help="Tipo de proyecto para cubicación (default arquitectonico)")
    parser.add_argument("--secciones", default=None,
                        help="YAML con secciones transversales del proyecto (ej: secciones_civiles.yaml)")
    parser.add_argument("--reattribute", action="store_true",
                        help="Aplicar reattribution post-hoc usando schedule")
    args = parser.parse_args()

    # ── Modo --from-json: carga recintos pre-extraídos, omite PDF y API ──────────
    if args.from_json:
        ruta_json = Path(args.from_json)
        if not ruta_json.exists():
            print(f"ERROR: '{ruta_json}' no existe")
            sys.exit(1)
        with open(ruta_json, encoding="utf-8") as f:
            datos = json.load(f)
        resultados = datos.get("resultados", [])
        schedules = {int(k): v for k, v in datos.get("schedules", {}).items()}
        print(f"\n📐 PoC Cubicación AI v5  [modo offline — sin API]")
        print(f"   {ruta_json.name}  |  {len(resultados)} lámina(s) cargadas\n")
    else:
        # ── Modo normal: extrae desde PDF via Claude API ───────────────────────
        if not args.pdf:
            parser.error("Se requiere 'pdf' o --from-json")
        ruta = Path(args.pdf)
        if not ruta.exists():
            print(f"ERROR: '{ruta}' no existe")
            sys.exit(1)

        doc = pymupdf.open(str(ruta))
        total_pags = len(doc)
        doc.close()

        indices = (
            [int(p.strip()) - 1 for p in args.paginas.split(",")]
            if args.paginas else list(range(total_pags))
        )
        indices = [i for i in indices if 0 <= i < total_pags]

        tiles_str = f"{args.tiles[0]}×{args.tiles[1]}" if args.tiles else "auto"
        print(f"\n📐 PoC Cubicación AI v5  [{MODELO}]")
        print(f"   {ruta.name}  |  págs {[i+1 for i in indices]}  |  {args.dpi}DPI  |  tiles={tiles_str}\n")

        client = _make_client()
        resultados = []
        schedules: dict[int, dict] = {}

        for idx in indices:
            try:
                res, sched = procesar_pagina(client, ruta, idx, total_pags, args.dpi, args.tiles)
                resultados.append(res)
                schedules[idx + 1] = sched
            except anthropic.APIError as e:
                print(f"    ERROR API: {e}")
                resultados.append({"error": str(e), "_pagina": idx + 1})
            except Exception as e:
                print(f"    ERROR: {e}")
                resultados.append({"error": str(e), "_pagina": idx + 1})

    # Reattribution opcional ANTES del resumen para que los Δ reflejen el resultado final
    if args.reattribute:
        from cubicador import reattribute_by_schedule
        for res in resultados:
            if "error" in res:
                continue
            pag = res.get("_pagina")
            sched = schedules.get(pag)
            if sched:
                log = reattribute_by_schedule(res, sched)
                if log.get("aplicado"):
                    print(f"  ↻ Reattribution pág {pag}: {log['rec']} {log['from']}→{log['to']} "
                          f"(error {log['error_antes']:.1f}% → {log['error_despues']:.1f}%)")

    imprimir_resumen(resultados, schedules)

    if args.json:
        out = {"resultados": resultados, "schedules": schedules}
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"  JSON guardado: {args.json}\n")

    if args.excel:
        try:
            from cubicador import cubicar, cubicar_electrico
            from presupuesto import cargar_precios, presupuestar, imprimir_presupuesto
            from excel import exportar_excel
        except ImportError as e:
            print(f"  ERROR: módulos cubicador/presupuesto/excel no disponibles: {e}")
            return

        alturas_override = {}
        if args.alturas:
            try:
                alturas_override = json.loads(args.alturas)
            except json.JSONDecodeError as e:
                print(f"  WARN: --alturas JSON inválido ({e}), ignorando")

        # Precios: electrico usa precios_electrico.csv por defecto cuando --tipo electrico
        if args.tipo == "electrico" and args.precios == "precios_cl.csv":
            precios_path = "precios_electrico.csv"
        else:
            precios_path = args.precios
        ruta_precios = Path(precios_path)
        if not ruta_precios.is_absolute():
            ruta_precios = Path(__file__).parent / ruta_precios
        if not ruta_precios.exists():
            print(f"  ERROR: precios no encontrados en {ruta_precios}")
            return
        precios = cargar_precios(ruta_precios)

        # Usar primera lámina para Excel (multi-página: agregar páginas extra como hojas adicionales en v6)
        primera = next((r for r in resultados if "error" not in r), None)
        if not primera:
            print("  ERROR: ninguna lámina procesada exitosamente")
            return

        pag = primera.get("_pagina")
        sched = schedules.get(pag)

        secciones = None
        if args.secciones:
            import yaml
            with open(args.secciones, encoding="utf-8") as _f:
                secciones = yaml.safe_load(_f)

        if args.tipo == "electrico":
            print(f"  Modo: cubicación eléctrica — altura pique {args.altura}m\n")
            cubicacion = cubicar_electrico(
                primera,
                altura_global=args.altura,
                alturas_override=alturas_override,
            )
            # Modo electrico: usar formato licitacion en lugar del Excel estándar
            try:
                from excel_licitacion import exportar_licitacion
                ruta_xlsx = exportar_licitacion(cubicacion, primera, args.excel)
                print(f"  Excel licitación guardado: {ruta_xlsx}\n")
            except Exception as e:
                print(f"  WARN: excel_licitacion falló ({e}), usando formato estándar")
                pres = presupuestar(cubicacion, precios, gg_utilidad=args.gg_utilidad, iva=args.iva)
                imprimir_presupuesto(pres)
                ruta_xlsx = exportar_excel(primera, sched, cubicacion, pres, args.excel)
                print(f"  Excel guardado: {ruta_xlsx}\n")
        else:
            cubicacion = cubicar(
                primera,
                altura_global=args.altura,
                alturas_override=alturas_override,
                incluir_comunes=args.incluir_comunes,
                secciones=secciones,
            )
            pres = presupuestar(cubicacion, precios, gg_utilidad=args.gg_utilidad, iva=args.iva)
            imprimir_presupuesto(pres)
            ruta_xlsx = exportar_excel(primera, sched, cubicacion, pres, args.excel)
            print(f"  Excel guardado: {ruta_xlsx}\n")


if __name__ == "__main__":
    main()
