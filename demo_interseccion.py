#!/usr/bin/env python3
"""
demo_interseccion.py — cubicacion urbana interseccion vial tipo Santiago

Caso sintetico: mejoramiento interseccion + ciclovias + mediana, comuna
de providencia. Cubre partidas civiles (~$200 MM CLP).
Nota: semaforización, canalizacion aguas lluvia y otros ítem no civiles
no están incluidos en este presupuesto.

Uso:
    python demo_interseccion.py
    python demo_interseccion.py --excel interseccion_cubicacion.xlsx
"""

import argparse
from pathlib import Path

from cubicador import cubicar
from presupuesto import cargar_precios, presupuestar, imprimir_presupuesto
from excel import exportar_excel

# Geometria interseccion 4 ramales (2 vias principales + 2 secundarias)
ANCHO_VIA_PRINCIPAL_M = 7.00   # 2 pistas, 3.5m c/u
ANCHO_VIA_SECUNDARIA_M = 6.00  # 2 pistas, 3.0m c/u
RADIO_CURVA_M = 8.00           # radio curva esquinas

LONGITUD_VP_M = 80.0   # 2 ramales via principal, cada uno
LONGITUD_VS_M = 60.0   # 2 ramales via secundaria, cada uno

# Areas principales
AREA_CALZADA_INTERSECCION = 28.0 * 28.0    # zona central interseccion ~784 m²
AREA_CALZADA_VP = 2 * LONGITUD_VP_M * ANCHO_VIA_PRINCIPAL_M   # 1,120 m²
AREA_CALZADA_VS = 2 * LONGITUD_VS_M * ANCHO_VIA_SECUNDARIA_M  # 720 m²

AREA_VEREDA_VP = 2 * LONGITUD_VP_M * 2.5  # veredas 2.5m ancho
AREA_VEREDA_VS = 2 * LONGITUD_VS_M * 2.0  # veredas 2.0m ancho

AREA_CICLOVIA = 2 * (LONGITUD_VP_M + LONGITUD_VS_M) * 2.0   # ciclovia 2m ancho

AREA_MEDIANA = 2 * LONGITUD_VP_M * 1.5    # mediana central verde via principal

# Demarcacion: marcas viales (cruces peatonales + lineas carril)
AREA_DEMARCACION = (28.0 * 4 * 0.5) + (LONGITUD_VP_M + LONGITUD_VS_M) * 2 * 0.3

# Señaletica: ~20 señales verticales en la interseccion
AREA_SENALES = 20 * 1.5   # 30 m²

# Iluminacion: 12 postes (3 por esquina)
AREA_ILUMINACION = 12 * 4.0   # 48 m²

# Cunetas ambos lados via principal
AREA_CUNETA = 2 * LONGITUD_VP_M * 0.4   # 64 m²

# Camino de acceso al parque (granular)
AREA_ACCESO_PARQUE = 60.0 * 4.0   # 240 m²

# Muro de contencion por diferencia de nivel (1 tramo)
AREA_MURO = 40.0 * 2.5   # 100 m²


def construir_resultado() -> dict:
    recintos = [
        {"nombre": "CALZADA INTERSECCION CENTRAL",
         "area_m2": round(AREA_CALZADA_INTERSECCION, 1),
         "confianza": 0.90, "departamento": "Interseccion"},
        {"nombre": "CALZADA VIA PRINCIPAL",
         "area_m2": round(AREA_CALZADA_VP, 1),
         "confianza": 0.92, "departamento": "Interseccion"},
        {"nombre": "CALZADA VIA SECUNDARIA",
         "area_m2": round(AREA_CALZADA_VS, 1),
         "confianza": 0.90, "departamento": "Interseccion"},
        {"nombre": "VEREDA VIA PRINCIPAL",
         "area_m2": round(AREA_VEREDA_VP, 1),
         "confianza": 0.88, "departamento": "Interseccion"},
        {"nombre": "VEREDA VIA SECUNDARIA",
         "area_m2": round(AREA_VEREDA_VS, 1),
         "confianza": 0.85, "departamento": "Interseccion"},
        {"nombre": "CICLOVIA SEGREGADA",
         "area_m2": round(AREA_CICLOVIA, 1),
         "confianza": 0.88, "departamento": "Interseccion"},
        {"nombre": "MEDIANA CENTRAL VIA PRINCIPAL",
         "area_m2": round(AREA_MEDIANA, 1),
         "confianza": 0.82, "departamento": "Interseccion"},
        {"nombre": "DEMARCACION VIAL CRUCE PEATONAL",
         "area_m2": round(AREA_DEMARCACION, 1),
         "confianza": 0.85, "departamento": "Interseccion"},
        {"nombre": "SENALETIVA VERTICAL",
         "area_m2": float(AREA_SENALES),
         "confianza": 0.80, "departamento": "Interseccion"},
        {"nombre": "ILUMINACION VIAL INTERSECCION",
         "area_m2": float(AREA_ILUMINACION),
         "confianza": 0.85, "departamento": "Interseccion"},
        {"nombre": "CUNETA REVESTIDA HORMIGON",
         "area_m2": round(AREA_CUNETA, 1),
         "confianza": 0.80, "departamento": "Interseccion"},
        {"nombre": "CAMINO DE SERVICIO PARQUE",
         "area_m2": round(AREA_ACCESO_PARQUE, 1),
         "confianza": 0.78, "departamento": "Interseccion"},
        {"nombre": "MURO DE CONTENCION DIFERENCIA NIVEL",
         "area_m2": float(AREA_MURO),
         "confianza": 0.82, "departamento": "Interseccion"},
    ]
    return {
        "pagina": 1,
        "pdf": "Planos_Interseccion_Providencia_2025.pdf",
        "recintos": recintos,
        "muros": {"exterior_ml": 0, "interior_ml": 0},
        "vanos": {"puertas": [], "ventanas": []},
        "schedule": {"tiene_tabla": False},
        "_tokens_entrada": 1800,
        "_tokens_salida": 210,
        "_costo_usd": 0.021,
        "_tiempo_s": 4.2,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo cubicacion interseccion urbana")
    parser.add_argument("--excel", default="interseccion_cubicacion.xlsx")
    parser.add_argument("--precios", default="precios_cl.csv")
    parser.add_argument("--gg-utilidad", type=float, default=0.25)
    parser.add_argument("--iva", type=float, default=0.19)
    args = parser.parse_args()

    print("=" * 70)
    print("  CUBICACION DEMO — Interseccion Urbana Providencia")
    print("  Mejoramiento vial + ciclovia + semaforización")
    print("  Presupuesto referencial obras civiles ~$200 MM CLP")
    print("=" * 70)
    print()

    resultado = construir_resultado()
    print(f"[1/4] Datos: {len(resultado['recintos'])} elementos detectados")
    for r in resultado["recintos"]:
        print(f"      {r['nombre']:<45} {r['area_m2']:>8,.0f} m²")
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
    ref_mm = 200.0
    diff_pct = (total_mm - ref_mm) / ref_mm * 100
    print()
    print(f"  Presupuesto referencial:  ${ref_mm:,.0f} MM CLP")
    print(f"  Nuestra estimacion:       ${total_mm:,.1f} MM CLP")
    print(f"  Diferencia:               {diff_pct:+.1f}%")
    if abs(diff_pct) < 20:
        print("  → Rango razonable para estimacion preliminar desde planos")
    else:
        print("  → Fuera de rango — revisar dimensiones y secciones")
    print()

    print(f"[4/4] Generando Excel → {args.excel}")
    exportar_excel(resultado, None, cub, pres, Path(args.excel))
    print(f"  [OK] {args.excel}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
