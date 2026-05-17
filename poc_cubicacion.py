#!/usr/bin/env python3
"""
PoC: Cubicación AI con Claude Vision
Uso: python poc_cubicacion.py plano.pdf
     python poc_cubicacion.py plano.pdf --paginas 1,2,3
     python poc_cubicacion.py plano.pdf --dpi 200
"""

import argparse
import base64
import json
import sys
import time
from pathlib import Path

import anthropic
import pymupdf


# ─── Configuración ────────────────────────────────────────────────────────────

MODELO = "claude-opus-4-7"
DPI_DEFAULT = 150        # 150 es suficiente para la mayoría; sube a 200 si el plano es muy denso
MAX_TOKENS = 4096
MAX_DIM_PX = 4000        # si la imagen supera esto, escala hacia abajo


PROMPT_EXTRACCION = """
Eres un cubicador profesional de construcción con experiencia en proyectos de arquitectura LATAM.
Analiza este plano arquitectónico y extrae los datos para una cubicación.

Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta (sin texto adicional):

{
  "lamina": {
    "titulo": "nombre o código de la lámina si es visible, si no null",
    "escala": "ej: 1:50 o 1:100 si es visible, si no null",
    "tipo": "planta | elevacion | corte | detalle | otro | desconocido"
  },
  "recintos": [
    {
      "nombre": "LIVING",
      "area_m2": 18.5,
      "confianza": 0.85,
      "nota": "área leída de cota / estimada por proporción / etc"
    }
  ],
  "muros": {
    "exterior_ml": null,
    "interior_ml": null,
    "confianza": 0.70,
    "nota": "cómo se estimó"
  },
  "vanos": {
    "puertas": [{"tipo": "simple 90cm", "cantidad": 3}],
    "ventanas": [{"tipo": "corredera 120x100", "cantidad": 4}]
  },
  "losas": {
    "area_m2": null,
    "confianza": 0.0,
    "nota": ""
  },
  "observaciones": "qué limitaciones encontraste en este plano",
  "calidad_plano": "alta | media | baja",
  "tiene_cotas": true,
  "tiene_escala_grafica": false
}

Reglas:
- Si no puedes determinar un valor con confianza, usa null (NO inventes números)
- confianza va de 0.0 a 1.0: usa 0.9+ solo si hay cota explícita, 0.5-0.7 si estimás por proporción
- Si el plano es escaneado, borroso o girado, indícalo en observaciones
- Solo extrae lo que realmente ves
"""


# ─── Funciones ────────────────────────────────────────────────────────────────

def pdf_pagina_a_base64(ruta_pdf: Path, numero_pagina: int, dpi: int) -> tuple[str, int, int]:
    """Convierte una página del PDF a PNG en base64. Retorna (b64, ancho, alto)."""
    doc = pymupdf.open(str(ruta_pdf))
    pagina = doc[numero_pagina]
    mat = pymupdf.Matrix(dpi / 72, dpi / 72)
    pix = pagina.get_pixmap(matrix=mat, alpha=False)

    # Escalar si supera el límite
    if pix.width > MAX_DIM_PX or pix.height > MAX_DIM_PX:
        factor = MAX_DIM_PX / max(pix.width, pix.height)
        mat2 = pymupdf.Matrix(factor * dpi / 72, factor * dpi / 72)
        pix = pagina.get_pixmap(matrix=mat2, alpha=False)

    png_bytes = pix.tobytes("png")
    b64 = base64.standard_b64encode(png_bytes).decode("utf-8")
    doc.close()
    return b64, pix.width, pix.height


def analizar_lamina(client: anthropic.Anthropic, b64: str, num_pagina: int) -> dict:
    """Llama a Claude Vision y retorna el JSON extraído."""
    response = client.messages.create(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64,
                    },
                },
                {"type": "text", "text": PROMPT_EXTRACCION},
            ],
        }],
    )

    texto = response.content[0].text.strip()

    # Limpiar markdown si Claude envuelve el JSON
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
    datos["_tokens_entrada"] = response.usage.input_tokens
    datos["_tokens_salida"] = response.usage.output_tokens
    return datos


def calcular_costo(tokens_entrada: int, tokens_salida: int) -> float:
    """Costo estimado en USD con claude-opus-4-7."""
    return (tokens_entrada * 15 + tokens_salida * 75) / 1_000_000


def imprimir_resumen(resultados: list[dict]) -> None:
    print("\n" + "═" * 60)
    print("  RESUMEN DE CUBICACIÓN")
    print("═" * 60)

    total_area = 0.0
    total_puertas = 0
    total_ventanas = 0
    total_costo = 0.0
    laminas_procesadas = 0

    for r in resultados:
        pagina = r.get("_pagina", "?")

        if "error" in r:
            print(f"\n  ✗ Lámina {pagina}: error de parseo")
            continue

        laminas_procesadas += 1
        lamina = r.get("lamina", {})
        tipo = lamina.get("tipo", "desconocido")
        escala = lamina.get("escala") or "no detectada"
        titulo = lamina.get("titulo") or "sin título"
        calidad = r.get("calidad_plano", "?")
        tiene_cotas = "✓" if r.get("tiene_cotas") else "✗"

        costo_lamina = calcular_costo(
            r.get("_tokens_entrada", 0), r.get("_tokens_salida", 0)
        )
        total_costo += costo_lamina

        print(f"\n  ── Lámina {pagina}: {titulo} ({tipo}) ──")
        print(f"     Escala: {escala}  |  Calidad: {calidad}  |  Cotas: {tiene_cotas}")

        recintos = r.get("recintos", [])
        if recintos:
            print(f"     Recintos ({len(recintos)}):")
            for rec in recintos:
                area = rec.get("area_m2")
                conf = rec.get("confianza", 0)
                area_str = f"{area:.1f} m²" if area else "sin área"
                conf_str = f"{conf:.0%}"
                flag = "⚠" if conf < 0.70 else "✓"
                print(f"       {flag} {rec['nombre']}: {area_str}  (confianza {conf_str})")
                if area:
                    total_area += area

        muros = r.get("muros", {})
        if muros.get("exterior_ml") or muros.get("interior_ml"):
            ext = f"{muros['exterior_ml']:.1f} ml" if muros.get("exterior_ml") else "?"
            inte = f"{muros['interior_ml']:.1f} ml" if muros.get("interior_ml") else "?"
            print(f"     Muros: exterior {ext}  |  interior {inte}")

        vanos = r.get("vanos", {})
        for p in vanos.get("puertas", []):
            total_puertas += p.get("cantidad", 0)
        for v in vanos.get("ventanas", []):
            total_ventanas += v.get("cantidad", 0)

        obs = r.get("observaciones", "")
        if obs:
            print(f"     ⚑ {obs}")

        print(f"     Costo API esta lámina: ${costo_lamina:.4f} USD")

    print("\n" + "─" * 60)
    print("  TOTALES AGREGADOS")
    print("─" * 60)
    print(f"  Láminas procesadas:  {laminas_procesadas}")
    print(f"  Área total recintos: {total_area:.1f} m²  ← validar contra planos")
    print(f"  Puertas detectadas:  {total_puertas} un")
    print(f"  Ventanas detectadas: {total_ventanas} un")
    print(f"  Costo total API:     ${total_costo:.4f} USD")
    print("═" * 60)

    if total_area > 0:
        print(f"\n  PASO SIGUIENTE:")
        print(f"  1. Compara {total_area:.1f} m² contra el área real del proyecto")
        print(f"  2. Los recintos con ⚠ (confianza < 70%) requieren verificación manual")
        print(f"  3. Si precisión > 75%: el PoC es viable ✓")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="PoC cubicación AI con Claude Vision")
    parser.add_argument("pdf", help="Ruta al PDF del plano arquitectónico")
    parser.add_argument("--paginas", help="Páginas a procesar, ej: 1,2,3 (base 1). Default: todas", default=None)
    parser.add_argument("--dpi", type=int, default=DPI_DEFAULT, help=f"DPI del renderizado (default {DPI_DEFAULT})")
    parser.add_argument("--json", help="Guardar resultados JSON en este archivo", default=None)
    args = parser.parse_args()

    ruta = Path(args.pdf)
    if not ruta.exists():
        print(f"ERROR: No se encontró el archivo '{ruta}'")
        sys.exit(1)

    doc = pymupdf.open(str(ruta))
    total_paginas = len(doc)
    doc.close()

    if args.paginas:
        indices = [int(p.strip()) - 1 for p in args.paginas.split(",")]
        indices = [i for i in indices if 0 <= i < total_paginas]
    else:
        indices = list(range(total_paginas))

    print(f"\n📐 PoC Cubicación AI")
    print(f"   Archivo:  {ruta.name}")
    print(f"   Páginas:  {[i+1 for i in indices]}  ({total_paginas} total en el PDF)")
    print(f"   DPI:      {args.dpi}")
    print(f"   Modelo:   {MODELO}")
    print()

    import os
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    token_file = os.environ.get("CLAUDE_SESSION_INGRESS_TOKEN_FILE")
    if base_url and token_file and not os.environ.get("ANTHROPIC_API_KEY"):
        session_token = Path(token_file).read_text().strip()
        client = anthropic.Anthropic(auth_token=session_token, base_url=base_url)
    else:
        client = anthropic.Anthropic()
    resultados = []

    for idx in indices:
        print(f"  → Procesando lámina {idx + 1}/{total_paginas}...", end=" ", flush=True)
        t0 = time.time()

        try:
            b64, ancho, alto = pdf_pagina_a_base64(ruta, idx, args.dpi)
            datos = analizar_lamina(client, b64, idx)
            elapsed = time.time() - t0
            costo = calcular_costo(datos.get("_tokens_entrada", 0), datos.get("_tokens_salida", 0))
            print(f"OK  ({elapsed:.1f}s, {ancho}×{alto}px, ${costo:.4f})")
        except anthropic.APIError as e:
            print(f"ERROR API: {e}")
            datos = {"error": str(e), "_pagina": idx + 1}
        except Exception as e:
            print(f"ERROR: {e}")
            datos = {"error": str(e), "_pagina": idx + 1}

        resultados.append(datos)

    imprimir_resumen(resultados)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)
        print(f"  Resultados guardados en: {args.json}\n")


if __name__ == "__main__":
    main()
