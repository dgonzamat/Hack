#!/usr/bin/env python3
"""
PoC: Cubicación AI con Claude Vision
Uso: python poc_cubicacion.py plano.pdf
     python poc_cubicacion.py plano.pdf --paginas 1,2,3
     python poc_cubicacion.py plano.pdf --dpi 200
     python poc_cubicacion.py plano.pdf --tiles 2x2   (forzar cuadrantes)
     python poc_cubicacion.py plano.pdf --tiles 1x1   (forzar imagen completa)
"""

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import anthropic
import pymupdf
from PIL import Image

# ─── Configuración ────────────────────────────────────────────────────────────

MODELO = "claude-opus-4-7"
DPI_DEFAULT = 180
MAX_TOKENS = 4096
TILE_MAX_PX = 2800       # máx px por lado de un tile antes de escalar
AUTO_TILE_THRESH = 3500  # si imagen supera este ancho → activar tiles automáticamente
TILE_OVERLAP = 0.12      # 12% de solapamiento entre tiles vecinos

POSICIONES = {
    (0, 0): "CUADRANTE SUPERIOR IZQUIERDO",
    (0, 1): "CUADRANTE SUPERIOR DERECHO",
    (1, 0): "CUADRANTE INFERIOR IZQUIERDO",
    (1, 1): "CUADRANTE INFERIOR DERECHO",
    (0, 2): "CUADRANTE SUPERIOR CENTRO",
    (1, 2): "CUADRANTE INFERIOR CENTRO",
}


def prompt_para_tile(posicion: str | None) -> str:
    ctx = f"\nESTÁS ANALIZANDO EL {posicion} del plano completo.\n" if posicion else ""
    return f"""Eres un cubicador profesional de construcción con experiencia en proyectos de arquitectura LATAM.
{ctx}
Analiza este plano arquitectónico (o fragmento de él) y extrae los datos para cubicación.
Si ves recintos cortados en el borde, inclúyelos con confianza reducida.

Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta (sin texto adicional):

{{
  "lamina": {{
    "titulo": "nombre o código si es visible, si no null",
    "escala": "ej: 1:75 o 1:100 si es visible, si no null",
    "tipo": "planta | elevacion | corte | detalle | otro | desconocido"
  }},
  "recintos": [
    {{
      "nombre": "LIVING COMEDOR",
      "area_m2": 28.4,
      "confianza": 0.90,
      "nota": "área leída de etiqueta / estimada por proporción"
    }}
  ],
  "muros": {{
    "exterior_ml": null,
    "interior_ml": null,
    "confianza": 0.70,
    "nota": "cómo se estimó"
  }},
  "vanos": {{
    "puertas": [{{"tipo": "simple 90cm", "cantidad": 3}}],
    "ventanas": [{{"tipo": "corredera 120x100", "cantidad": 4}}]
  }},
  "losas": {{
    "area_m2": null,
    "confianza": 0.0,
    "nota": ""
  }},
  "observaciones": "limitaciones encontradas",
  "calidad_plano": "alta | media | baja",
  "tiene_cotas": true,
  "tiene_escala_grafica": false
}}

Reglas CRÍTICAS:
- Lee etiquetas de área dentro de cada recinto antes de estimar
- Si hay una tabla de áreas visible, léela y úsala
- confianza 0.9+ = cota o etiqueta explícita | 0.6-0.8 = estimado | <0.5 = muy incierto
- USA null si no puedes determinar — NUNCA inventes números
- Incluye TODOS los recintos visibles, incluso los parcialmente cortados
"""


# ─── Renderizado y tiling ──────────────────────────────────────────────────────

def _pix_to_b64(pix: pymupdf.Pixmap) -> str:
    return base64.standard_b64encode(pix.tobytes("png")).decode("utf-8")


def render_pagina(ruta_pdf: Path, num_pag: int, dpi: int) -> pymupdf.Pixmap:
    doc = pymupdf.open(str(ruta_pdf))
    pix = doc[num_pag].get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), alpha=False)
    doc.close()
    return pix


def pix_to_pil(pix: pymupdf.Pixmap) -> Image.Image:
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def generar_tiles(img: Image.Image, nx: int, ny: int, overlap: float) -> list[dict]:
    """Divide img en nx×ny tiles con solapamiento. Retorna lista de dicts con b64 e info."""
    W, H = img.size
    tw = W / nx
    th = H / ny
    pad_x = int(tw * overlap)
    pad_y = int(th * overlap)
    tiles = []

    for row in range(ny):
        for col in range(nx):
            x0 = max(0, int(col * tw) - pad_x)
            y0 = max(0, int(row * th) - pad_y)
            x1 = min(W, int((col + 1) * tw) + pad_x)
            y1 = min(H, int((row + 1) * th) + pad_y)

            tile_img = img.crop((x0, y0, x1, y1))

            # Escalar si supera TILE_MAX_PX
            tw_px, th_px = tile_img.size
            if max(tw_px, th_px) > TILE_MAX_PX:
                factor = TILE_MAX_PX / max(tw_px, th_px)
                tile_img = tile_img.resize(
                    (int(tw_px * factor), int(th_px * factor)), Image.LANCZOS
                )

            import io
            buf = io.BytesIO()
            tile_img.save(buf, format="PNG")
            b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")

            posicion = POSICIONES.get((row, col), f"SECCIÓN {row+1},{col+1}")
            tiles.append({
                "b64": b64,
                "row": row,
                "col": col,
                "posicion": posicion,
                "size": tile_img.size,
                "bbox": (x0, y0, x1, y1),
            })
    return tiles


# ─── Llamada a Claude ──────────────────────────────────────────────────────────

def analizar_imagen(
    client: anthropic.Anthropic,
    b64: str,
    num_pagina: int,
    posicion: str | None = None,
) -> dict:
    response = client.messages.create(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": prompt_para_tile(posicion)},
            ],
        }],
    )
    texto = response.content[0].text.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    texto = texto.strip()
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        datos = {"error": "JSON inválido", "raw": texto[:500]}
    datos["_pagina"] = num_pagina + 1
    datos["_posicion"] = posicion
    datos["_tokens_entrada"] = response.usage.input_tokens
    datos["_tokens_salida"] = response.usage.output_tokens
    return datos


# ─── Merge de tiles ────────────────────────────────────────────────────────────

def _norm(nombre: str) -> str:
    """Normaliza nombre de recinto para comparación."""
    return nombre.upper().strip().replace("-", " ").replace("/", " ")


def merge_resultados_tiles(tile_results: list[dict], num_pagina: int) -> dict:
    """
    Fusiona resultados de múltiples tiles en un único resultado de lámina.
    Estrategia: para recintos duplicados, queda el de mayor confianza.
    Para vanos y muros, suma o toma el máximo.
    """
    if not tile_results:
        return {"error": "sin resultados", "_pagina": num_pagina + 1}

    # Metadatos de lámina: del primer tile no-error que tenga datos
    lamina_info = {"titulo": None, "escala": None, "tipo": "desconocido"}
    escala_grafica = False
    tiene_cotas = False
    calidades = []
    observaciones = []
    tokens_entrada = 0
    tokens_salida = 0

    for t in tile_results:
        if "error" in t:
            continue
        tokens_entrada += t.get("_tokens_entrada", 0)
        tokens_salida += t.get("_tokens_salida", 0)
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

    # Calidad: si alguno es alta, alta; si alguno media, media; sino baja
    if "alta" in calidades:
        calidad_final = "alta"
    elif "media" in calidades:
        calidad_final = "media"
    else:
        calidad_final = "baja"

    # Recintos: deduplicar por nombre normalizado, quedarse con mayor confianza
    recintos_map: dict[str, dict] = {}
    for t in tile_results:
        for rec in t.get("recintos", []):
            nombre = rec.get("nombre", "")
            if not nombre:
                continue
            key = _norm(nombre)
            existente = recintos_map.get(key)
            conf_nuevo = rec.get("confianza", 0) or 0
            if existente is None:
                recintos_map[key] = rec
            else:
                conf_existente = existente.get("confianza", 0) or 0
                # Prefiere el que tenga area y mayor confianza
                tiene_area_nuevo = rec.get("area_m2") is not None
                tiene_area_exist = existente.get("area_m2") is not None
                if tiene_area_nuevo and (not tiene_area_exist or conf_nuevo > conf_existente):
                    recintos_map[key] = rec

    recintos_final = sorted(recintos_map.values(), key=lambda r: r.get("nombre", ""))

    # Muros: sumar ml de todos los tiles (cada tile ve una zona distinta)
    ext_total = 0.0
    int_total = 0.0
    muro_conf = 0.0
    muro_nota = ""
    for t in tile_results:
        m = t.get("muros", {})
        if m.get("exterior_ml"):
            ext_total += m["exterior_ml"]
        if m.get("interior_ml"):
            int_total += m["interior_ml"]
        c = m.get("confianza", 0) or 0
        if c > muro_conf:
            muro_conf = c
            muro_nota = m.get("nota", "")

    # Vanos: sumar por tipo entre tiles (evitar doble conteo con solapamiento)
    # Con solapamiento 12%, un vano en el borde puede aparecer en 2 tiles
    # Estrategia conservadora: sumar y luego descontar ~15% si hay más de 1 tile
    n_tiles = len([t for t in tile_results if "error" not in t])
    puertas_map: dict[str, int] = {}
    ventanas_map: dict[str, int] = {}
    for t in tile_results:
        v = t.get("vanos", {})
        for p in v.get("puertas", []):
            tipo = p.get("tipo", "desconocido")
            puertas_map[tipo] = puertas_map.get(tipo, 0) + p.get("cantidad", 0)
        for w in v.get("ventanas", []):
            tipo = w.get("tipo", "desconocido")
            ventanas_map[tipo] = ventanas_map.get(tipo, 0) + w.get("cantidad", 0)

    # Descontar solapamiento si más de 1 tile
    if n_tiles > 1:
        puertas_map = {k: max(1, round(v * (1 - TILE_OVERLAP))) for k, v in puertas_map.items()}
        ventanas_map = {k: max(1, round(v * (1 - TILE_OVERLAP))) for k, v in ventanas_map.items()}

    return {
        "_pagina": num_pagina + 1,
        "_tiles_procesados": n_tiles,
        "_tokens_entrada": tokens_entrada,
        "_tokens_salida": tokens_salida,
        "lamina": lamina_info,
        "recintos": recintos_final,
        "muros": {
            "exterior_ml": round(ext_total, 1) if ext_total else None,
            "interior_ml": round(int_total, 1) if int_total else None,
            "confianza": round(muro_conf, 2),
            "nota": muro_nota,
        },
        "vanos": {
            "puertas": [{"tipo": k, "cantidad": v} for k, v in puertas_map.items()],
            "ventanas": [{"tipo": k, "cantidad": v} for k, v in ventanas_map.items()],
        },
        "losas": {"area_m2": None, "confianza": 0.0, "nota": ""},
        "observaciones": " | ".join(observaciones),
        "calidad_plano": calidad_final,
        "tiene_cotas": tiene_cotas,
        "tiene_escala_grafica": escala_grafica,
    }


# ─── Costo ────────────────────────────────────────────────────────────────────

def calcular_costo(tokens_entrada: int, tokens_salida: int) -> float:
    return (tokens_entrada * 15 + tokens_salida * 75) / 1_000_000


# ─── Output ───────────────────────────────────────────────────────────────────

def imprimir_resumen(resultados: list[dict]) -> None:
    print("\n" + "═" * 64)
    print("  RESUMEN DE CUBICACIÓN")
    print("═" * 64)

    total_area = 0.0
    total_puertas = 0
    total_ventanas = 0
    total_costo = 0.0
    laminas_procesadas = 0

    for r in resultados:
        pagina = r.get("_pagina", "?")
        if "error" in r:
            print(f"\n  ✗ Lámina {pagina}: {r.get('error','error')}")
            continue

        laminas_procesadas += 1
        lam = r.get("lamina", {})
        titulo = lam.get("titulo") or "sin título"
        tipo = lam.get("tipo", "?")
        escala = lam.get("escala") or "no detectada"
        calidad = r.get("calidad_plano", "?")
        cotas = "✓" if r.get("tiene_cotas") else "✗"
        tiles_n = r.get("_tiles_procesados", 1)
        modo = f"tiles×{tiles_n}" if tiles_n > 1 else "completa"

        costo = calcular_costo(r.get("_tokens_entrada", 0), r.get("_tokens_salida", 0))
        total_costo += costo

        print(f"\n  ── Lámina {pagina}: {titulo} ({tipo}) [{modo}] ──")
        print(f"     Escala: {escala}  |  Calidad: {calidad}  |  Cotas: {cotas}")

        recintos = r.get("recintos", [])
        sin_area = [rec for rec in recintos if rec.get("area_m2") is None]
        con_area = [rec for rec in recintos if rec.get("area_m2") is not None]

        if recintos:
            print(f"     Recintos: {len(con_area)} con área  +  {len(sin_area)} sin área")
            for rec in recintos:
                area = rec.get("area_m2")
                conf = rec.get("confianza") or 0
                area_str = f"{area:.1f} m²" if area else "sin área"
                flag = "✓" if conf >= 0.70 else "⚠"
                print(f"       {flag} {rec['nombre']}: {area_str}  ({conf:.0%})")
                if area:
                    total_area += area

        m = r.get("muros", {})
        if m.get("exterior_ml") or m.get("interior_ml"):
            ext = f"{m['exterior_ml']:.1f} ml" if m.get("exterior_ml") else "?"
            inte = f"{m['interior_ml']:.1f} ml" if m.get("interior_ml") else "?"
            print(f"     Muros:   exterior {ext}  |  interior {inte}")

        v = r.get("vanos", {})
        n_p = sum(p.get("cantidad", 0) for p in v.get("puertas", []))
        n_v = sum(w.get("cantidad", 0) for w in v.get("ventanas", []))
        total_puertas += n_p
        total_ventanas += n_v

        obs = r.get("observaciones", "")
        if obs:
            for line in obs.split(" | "):
                if line.strip():
                    print(f"     ⚑ {line.strip()[:120]}")

        print(f"     Costo API: ${costo:.4f} USD")

    print("\n" + "─" * 64)
    print("  TOTALES")
    print("─" * 64)
    print(f"  Láminas procesadas: {laminas_procesadas}")
    print(f"  Área total recintos: {total_area:.1f} m²")
    print(f"  Puertas detectadas:  {total_puertas} un")
    print(f"  Ventanas detectadas: {total_ventanas} un")
    print(f"  Costo total API:     ${total_costo:.4f} USD")
    print("═" * 64)

    if total_area > 0:
        print(f"\n  SIGUIENTE:")
        print(f"  · Compara {total_area:.1f} m² contra área real del proyecto")
        print(f"  · Recintos ⚠ (confianza < 70%) requieren verificación manual")
        print(f"  · Precisión > 75% → PoC viable ✓")
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
    """Parsea '2x2' → (2, 2), '1x1' → (1, 1)."""
    partes = valor.lower().split("x")
    if len(partes) == 2:
        return int(partes[0]), int(partes[1])
    raise argparse.ArgumentTypeError(f"Formato tiles inválido: '{valor}'. Usa NxM, ej: 2x2")


def main() -> None:
    parser = argparse.ArgumentParser(description="PoC cubicación AI — con tiling para planos densos")
    parser.add_argument("pdf", help="Ruta al PDF del plano arquitectónico")
    parser.add_argument("--paginas", default=None, help="Páginas a procesar, ej: 1,2,3 (base 1)")
    parser.add_argument("--dpi", type=int, default=DPI_DEFAULT, help=f"DPI del renderizado (default {DPI_DEFAULT})")
    parser.add_argument("--tiles", type=_parse_tiles, default=None,
                        help="Grid de tiles, ej: 2x2. Auto-detectado si no se especifica.")
    parser.add_argument("--json", default=None, help="Guardar resultados JSON en este archivo")
    args = parser.parse_args()

    ruta = Path(args.pdf)
    if not ruta.exists():
        print(f"ERROR: archivo no encontrado: '{ruta}'")
        sys.exit(1)

    doc = pymupdf.open(str(ruta))
    total_pags = len(doc)
    doc.close()

    indices = (
        [int(p.strip()) - 1 for p in args.paginas.split(",")]
        if args.paginas else list(range(total_pags))
    )
    indices = [i for i in indices if 0 <= i < total_pags]

    print(f"\n📐 PoC Cubicación AI  (modelo: {MODELO})")
    print(f"   Archivo : {ruta.name}")
    print(f"   Páginas : {[i+1 for i in indices]}  (total {total_pags})")
    print(f"   DPI     : {args.dpi}")
    tiles_arg = f"{args.tiles[0]}×{args.tiles[1]}" if args.tiles else "auto"
    print(f"   Tiles   : {tiles_arg}")
    print()

    client = _make_client()
    resultados = []

    for idx in indices:
        print(f"  Lámina {idx+1}/{total_pags}:")
        t0 = time.time()

        try:
            pix = render_pagina(ruta, idx, args.dpi)
            img = pix_to_pil(pix)
            W, H = img.size
            print(f"    Renderizado: {W}×{H}px")

            # Decidir grid de tiles
            if args.tiles:
                nx, ny = args.tiles
            elif W > AUTO_TILE_THRESH:
                nx, ny = 2, 2
                print(f"    Imagen densa → tiling automático 2×2")
            else:
                nx, ny = 1, 1

            if nx == 1 and ny == 1:
                # Imagen completa — escalar si es muy grande
                if max(W, H) > TILE_MAX_PX:
                    factor = TILE_MAX_PX / max(W, H)
                    img_s = img.resize((int(W * factor), int(H * factor)), Image.LANCZOS)
                else:
                    img_s = img
                import io
                buf = io.BytesIO(); img_s.save(buf, "PNG")
                b64 = base64.standard_b64encode(buf.getvalue()).decode()
                print(f"    → analizando imagen completa ({img_s.size[0]}×{img_s.size[1]}px)...", end=" ", flush=True)
                datos = analizar_imagen(client, b64, idx)
                elapsed = time.time() - t0
                costo = calcular_costo(datos.get("_tokens_entrada", 0), datos.get("_tokens_salida", 0))
                print(f"OK ({elapsed:.1f}s, ${costo:.4f})")
                resultados.append(datos)
            else:
                tiles = generar_tiles(img, nx, ny, TILE_OVERLAP)
                tile_results = []
                for tile in tiles:
                    pos = tile["posicion"]
                    sz = tile["size"]
                    print(f"    → {pos} ({sz[0]}×{sz[1]}px)...", end=" ", flush=True)
                    t1 = time.time()
                    try:
                        res = analizar_imagen(client, tile["b64"], idx, posicion=pos)
                        costo = calcular_costo(res.get("_tokens_entrada", 0), res.get("_tokens_salida", 0))
                        n_rec = len(res.get("recintos", []))
                        print(f"OK ({time.time()-t1:.1f}s, {n_rec} recintos, ${costo:.4f})")
                        tile_results.append(res)
                    except Exception as e:
                        print(f"ERROR: {e}")
                        tile_results.append({"error": str(e), "_pagina": idx + 1, "_posicion": pos})

                merged = merge_resultados_tiles(tile_results, idx)
                elapsed = time.time() - t0
                print(f"    Merge: {len(merged.get('recintos', []))} recintos únicos — total {elapsed:.1f}s")
                resultados.append(merged)

        except Exception as e:
            print(f"    ERROR: {e}")
            resultados.append({"error": str(e), "_pagina": idx + 1})

    imprimir_resumen(resultados)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)
        print(f"  JSON guardado: {args.json}\n")


if __name__ == "__main__":
    main()
