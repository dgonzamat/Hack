#!/usr/bin/env python3
"""
demo_conservacion.py — cubicacion conservacion periodica ruta 5 sur tramo tipo

Caso sintetico: contrato de conservacion periodica + mantenimiento de seguridad
vial para un tramo de 30 km en Ruta 5 Sur. Presupuesto referencial $2.800 MM CLP.

Partidas cubiertas: recarpeteo, micropavimento, sello grietas, senalizacion,
demarcacion, guardavias, hitos kilometricos, balizas, bajadas de agua, revegetacion.

Uso:
    python demo_conservacion.py
    python demo_conservacion.py --excel conservacion_cubicacion.xlsx
"""

import argparse
from pathlib import Path

from cubicador import cubicar
from presupuesto import cargar_precios, presupuestar, imprimir_presupuesto
from excel import exportar_excel

# Geometria del tramo
LONGITUD_M = 30_000       # 30 km ruta bidireccional
ANCHO_CALZADA_M = 7.00    # 2 pistas 3.5m (norma basica)
ANCHO_BERMA_M = 0.50      # berma consolidada

# Conservacion de calzada
# 40% del tramo requiere recarpeteo full
AREA_RECARPETEO = round(LONGITUD_M * 0.40 * (ANCHO_CALZADA_M + 2 * ANCHO_BERMA_M))
# 30% requiere micropavimento (menor deterioro superficial)
AREA_MICROPAVIMENTO = round(LONGITUD_M * 0.30 * (ANCHO_CALZADA_M + 2 * ANCHO_BERMA_M))
# 30% solo sello de grietas
AREA_SELLO_GRIETAS = round(LONGITUD_M * 0.30 * (ANCHO_CALZADA_M + 2 * ANCHO_BERMA_M))

# Demarcacion horizontal completa del tramo (ambas pistas + bordes)
AREA_DEMARCACION = round(LONGITUD_M * 1.8)   # lineas eje + bordes ~1.8m efectivo por km

# Senaletiva vertical: renovacion 40% de senales (1 c/150m → 200 señales)
AREA_SENALES = 200 * 1.5   # 300 m²

# Balizas y delineadores (500 unidades, 1.5 m² por unidad como huella panel)
AREA_BALIZAS = 500 * 1.5   # 750 m²

# Hitos kilometricos (km 0 a km 30 = 60 hitos, 1.5 m² cada uno)
AREA_HITOS = 60 * 1.5      # 90 m²

# Guardavias: renovacion 8 km de guardavia deteriorada
AREA_GUARDAVIA = 8_000 * 0.5   # 4,000 m² (0.5m ancho)

# Bajadas de agua (cunetas transversales en talud): cada 500m → 60 bajadas
AREA_BAJADAS_AGUA = 60 * 8.0 * 2.0   # 60 bajadas × 8m largo × 2m ancho = 960 m²

# Revegetacion de taludes deteriorados
AREA_REVEGETACION = round(LONGITUD_M * 0.15 * 3.0)   # 15% del tramo, talud 3m alto


def construir_resultado() -> dict:
    recintos = [
        {"nombre": "RECARPETEO ASFALTICO ZONA A",
         "area_m2": float(AREA_RECARPETEO),
         "confianza": 0.92, "departamento": "Conservacion"},
        {"nombre": "MICROPAVIMENTO ZONA B",
         "area_m2": float(AREA_MICROPAVIMENTO),
         "confianza": 0.90, "departamento": "Conservacion"},
        {"nombre": "SELLO DE GRIETAS ZONA C",
         "area_m2": float(AREA_SELLO_GRIETAS),
         "confianza": 0.90, "departamento": "Conservacion"},
        {"nombre": "DEMARCACION VIAL TERMOPLASTICA",
         "area_m2": float(AREA_DEMARCACION),
         "confianza": 0.92, "departamento": "Seguridad Vial"},
        {"nombre": "SENALETIVA VERTICAL RENOVACION",
         "area_m2": float(AREA_SENALES),
         "confianza": 0.88, "departamento": "Seguridad Vial"},
        {"nombre": "BALIZAS RETROREFLECTANTES",
         "area_m2": float(AREA_BALIZAS),
         "confianza": 0.85, "departamento": "Seguridad Vial"},
        {"nombre": "HITO KILOMETRICO TRAMO",
         "area_m2": float(AREA_HITOS),
         "confianza": 0.88, "departamento": "Seguridad Vial"},
        {"nombre": "GUARDAVIA FLEXIBLE W RENOVACION",
         "area_m2": float(AREA_GUARDAVIA),
         "confianza": 0.90, "departamento": "Seguridad Vial"},
        {"nombre": "BAJADA DE AGUA TALUD",
         "area_m2": float(AREA_BAJADAS_AGUA),
         "confianza": 0.82, "departamento": "Drenaje"},
        {"nombre": "REVEGETACION TALUDES DETERIORADOS",
         "area_m2": float(AREA_REVEGETACION),
         "confianza": 0.85, "departamento": "Medioambiente"},
    ]
    return {
        "pagina": 1,
        "pdf": "Proyecto_Conservacion_Ruta5_Sur_2025.pdf",
        "recintos": recintos,
        "muros": {"exterior_ml": 0, "interior_ml": 0},
        "vanos": {"puertas": [], "ventanas": []},
        "schedule": {"tiene_tabla": False},
        "_tokens_entrada": 1200,
        "_tokens_salida": 150,
        "_costo_usd": 0.015,
        "_tiempo_s": 3.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo conservacion vial")
    parser.add_argument("--excel", default="conservacion_cubicacion.xlsx")
    parser.add_argument("--precios", default="precios_cl.csv")
    parser.add_argument("--gg-utilidad", type=float, default=0.25)
    parser.add_argument("--iva", type=float, default=0.19)
    args = parser.parse_args()

    print("=" * 70)
    print("  CUBICACION DEMO — Conservacion Periodica Ruta 5 Sur")
    print("  Recarpeteo + micropavimento + seguridad vial (30 km)")
    print("  Presupuesto referencial obras civiles ~$3.200 MM CLP")
    print("=" * 70)
    print()

    resultado = construir_resultado()
    print(f"[1/4] Datos: {len(resultado['recintos'])} elementos detectados")
    for r in resultado["recintos"]:
        print(f"      {r['nombre']:<45} {r['area_m2']:>10,.0f} m²")
    print()

    print("[2/4] Cubicando...")
    cub = cubicar(resultado, altura_global=2.4)
    partidas = cub["partidas"]
    print(f"\n      Partidas generadas: {len(partidas)}")
    print()
    print(f"{'PARTIDA':<40} {'UNIDAD':>8} {'CANTIDAD':>12}")
    print("-" * 62)
    for p in partidas:
        print(f"  {p['partida']:<38} {p['unidad']:>8} {p['cantidad']:>12,.1f}")
    print()

    precios_path = Path(args.precios)
    if not precios_path.exists():
        print(f"[!] No se encontro {precios_path}, omitiendo presupuesto")
        return

    print("[3/4] Presupuestando...")
    precios = cargar_precios(precios_path)
    pres = presupuestar(cub, precios, gg_utilidad=args.gg_utilidad, iva=args.iva)
    print()
    imprimir_presupuesto(pres)
    print()

    total_mm = pres["subtotales"]["total_con_iva"] / 1_000_000
    ref_mm = 3_200.0
    diff_pct = (total_mm - ref_mm) / ref_mm * 100
    print()
    print(f"  Presupuesto referencial:  ${ref_mm:,.0f} MM CLP")
    print(f"  Nuestra estimacion:       ${total_mm:,.1f} MM CLP")
    print(f"  Diferencia:               {diff_pct:+.1f}%")
    if abs(diff_pct) < 25:
        print("  → Rango razonable para estimacion preliminar desde planos")
    else:
        print("  → Fuera de rango — revisar dimensiones y precios unitarios")
    print()

    print(f"[4/4] Generando Excel → {args.excel}")
    exportar_excel(resultado, None, cub, pres, Path(args.excel))
    print(f"  [OK] {args.excel}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
