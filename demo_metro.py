#!/usr/bin/env python3
"""
demo_metro.py — cubicacion obras civiles estacion metro tipo (L7 Metro Santiago)

Caso sintetico basado en EIA Linea 7 Metro Santiago (2020) y Manual de Diseno
Metro S.A. Modela estacion intermedia tipo con tuneles TBM, galeria de bypass,
andenes, muros pantalla y movimiento de tierras.

Solo obras civiles estructurales (sin MEP, sin terminaciones, sin via).
Presupuesto referencial obras civiles estructurales: ~$9.000 MM CLP.

Ref: EIA L7 Metro Santiago (2020), Manual de Carreteras MOP Vol.5 Cap.10,
     Norma ITA para impermeabilizacion, EFE Norma Via 2019.

Uso:
    python demo_metro.py
    python demo_metro.py --excel metro_cubicacion.xlsx
"""

import argparse
import math
from pathlib import Path

from cubicador import cubicar_vial
from presupuesto import cargar_precios, presupuestar, imprimir_presupuesto
from excel import exportar_excel

# ── Geometria de la estacion ────────────────────────────────────────────────
# Tuneles TBM: 2 tubos independientes (Norte y Sur) Ø6.10m
# Longitud modelada: 300 m por tubo (zona de plataforma + accesos)
LONG_TBM_M = 300.0       # longitud por tubo TBM
DIAM_TBM_M = 6.10        # diametro excavacion TBM (EIA L7)

# Andenes laterales: 2 × 120m × 4.8m
LONG_ANDEN_M = 120.0
ANCHO_ANDEN_M = 4.80     # anden lateral tipo L7

# Vestibulo mezzanine (caja de hormigon): 120m × 16m
LONG_VESTIBULO_M = 120.0
ANCHO_VESTIBULO_M = 16.0

# Galerias
GALERIA_ACCESO_M = 35.0   # longitud galeria de acceso superficial
ANCHO_GALERIA_M = 4.20    # seccion 4.2×4.5m (galeria tipo L7)
GALERIA_BYPASS_M = 90.0   # galeria de bypass / evacuacion entre tubos

# Muros pantalla (caja del vestibulo): 2 lados × 120m × 12m (altura excavacion)
LARGO_MURO_PANTALLA_M = 120.0
ALTO_MURO_PANTALLA_M = 12.0

# Corte caja estacion: area planta 120m × 20m, profundidad media 14m
AREA_CORTE_CAJA_M2 = 120.0 * 20.0

# Escarpe y preparacion superficial: franja 200m × 60m
AREA_ESCARPE_M2 = 200.0 * 60.0

# Terraplen accesos: rampas de acceso superficial
AREA_TERRAPLEN_M2 = 4 * 40.0 * 8.0   # 4 accesos × 40m largo × 8m ancho

# Via ferrea metro (2 vias): 2 × 300m × 1.44m (ancho plan via UIC)
AREA_VIA_M2 = 2 * LONG_TBM_M * 1.44


def construir_resultado() -> dict:
    """Construye estructura de resultado sin llamar a Claude (demo sintetico)."""
    area_tubo = LONG_TBM_M * DIAM_TBM_M
    area_anden = LONG_ANDEN_M * ANCHO_ANDEN_M
    area_vestibulo_muros = 2 * LONG_VESTIBULO_M * ALTO_MURO_PANTALLA_M
    area_galeria_acceso = GALERIA_ACCESO_M * ANCHO_GALERIA_M
    area_galeria_bypass = GALERIA_BYPASS_M * ANCHO_GALERIA_M

    recintos = [
        # Tuneles TBM (seccion circular D=6.10m)
        {"nombre": "TUNEL METRO TBM TUBO NORTE", "area_m2": area_tubo,
         "confianza": 0.97, "departamento": "Tunel"},
        {"nombre": "TUNEL METRO TBM TUBO SUR", "area_m2": area_tubo,
         "confianza": 0.97, "departamento": "Tunel"},
        # Andenes: tratados como vereda (losa hormigon)
        {"nombre": "ANDEN LATERAL NORTE", "area_m2": area_anden,
         "confianza": 0.95, "departamento": "Anden"},
        {"nombre": "ANDEN LATERAL SUR", "area_m2": area_anden,
         "confianza": 0.95, "departamento": "Anden"},
        # Muros pantalla de la caja
        {"nombre": "MURO PANTALLA NORTE", "area_m2": LARGO_MURO_PANTALLA_M * ALTO_MURO_PANTALLA_M,
         "confianza": 0.93, "departamento": "Estructura"},
        {"nombre": "MURO PANTALLA SUR", "area_m2": LARGO_MURO_PANTALLA_M * ALTO_MURO_PANTALLA_M,
         "confianza": 0.93, "departamento": "Estructura"},
        # Galerias (seccion rectangular 4.2×4.5m)
        {"nombre": "GALERIA DE ACCESO NORTE 1", "area_m2": area_galeria_acceso,
         "confianza": 0.92, "departamento": "Galeria"},
        {"nombre": "GALERIA DE ACCESO NORTE 2", "area_m2": area_galeria_acceso,
         "confianza": 0.92, "departamento": "Galeria"},
        {"nombre": "GALERIA DE ACCESO SUR 1", "area_m2": area_galeria_acceso,
         "confianza": 0.92, "departamento": "Galeria"},
        {"nombre": "GALERIA DE ACCESO SUR 2", "area_m2": area_galeria_acceso,
         "confianza": 0.92, "departamento": "Galeria"},
        {"nombre": "GALERIA DE EVACUACION BYPASS", "area_m2": area_galeria_bypass,
         "confianza": 0.90, "departamento": "Galeria"},
        # Movimiento de tierras
        {"nombre": "CORTE EN ROCA CAJA ESTACION", "area_m2": AREA_CORTE_CAJA_M2,
         "confianza": 0.93, "departamento": "Movimiento Tierras"},
        {"nombre": "TERRAPLEN RAMPAS ACCESO", "area_m2": AREA_TERRAPLEN_M2,
         "confianza": 0.90, "departamento": "Movimiento Tierras"},
        {"nombre": "ESCARPE Y LIMPIEZA TERRENO", "area_m2": AREA_ESCARPE_M2,
         "confianza": 0.95, "departamento": "Movimiento Tierras"},
        # Via ferrea metro
        {"nombre": "VIA FERREA METRO TUBO NORTE", "area_m2": AREA_VIA_M2 / 2,
         "confianza": 0.94, "departamento": "Via"},
        {"nombre": "VIA FERREA METRO TUBO SUR", "area_m2": AREA_VIA_M2 / 2,
         "confianza": 0.94, "departamento": "Via"},
    ]
    return {
        "pagina": 1,
        "pdf": "Estacion_Metro_Tipo_L7_2025.pdf",
        "recintos": recintos,
        "muros": {"exterior_ml": 0, "interior_ml": 0},
        "vanos": {"puertas": [], "ventanas": []},
        "schedule": {"tiene_tabla": False},
        "_tokens_entrada": 1800,
        "_tokens_salida": 200,
        "_costo_usd": 0.022,
        "_tiempo_s": 4.2,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo obras civiles estacion metro tipo L7")
    parser.add_argument("--excel", default="metro_cubicacion.xlsx")
    parser.add_argument("--precios", default="precios_cl.csv")
    parser.add_argument("--gg-utilidad", type=float, default=0.25)
    parser.add_argument("--iva", type=float, default=0.19)
    args = parser.parse_args()

    print("=" * 72)
    print("  CUBICACION DEMO — Estacion Metro Tipo (L7 Metro Santiago)")
    print("  Obras civiles estructurales: tuneles TBM + galeria + muros + via")
    print("  Ref: EIA L7 (2020) / Manual de Carreteras MOP / EFE Norma Via 2019")
    print("  Presupuesto referencial obras civiles: ~$9.000 MM CLP")
    print("=" * 72)
    print()

    resultado = construir_resultado()
    print(f"[1/4] Datos: {len(resultado['recintos'])} elementos detectados")
    for r in resultado["recintos"]:
        print(f"      {r['nombre']:<50} {r['area_m2']:>8,.0f} m²")
    print()

    print("[2/4] Cubicando (secciones civiles EIA L7 / Manual de Carreteras)...")
    # Secciones especificas EIA L7 Metro Santiago
    secciones_metro = {
        "tunel_metro": {
            "diametro_excav_m": 6.10,
            "espesor_dovelas_m": 0.30,
            "kg_acero_por_m3_dovela": 110,
            "impermeabilizacion": True,
        },
        "galeria": {
            "ancho_excav_m": 4.20,
            "alto_excav_m": 4.50,
            "espesor_revestimiento_m": 0.30,
            "kg_acero_por_m3_revest": 70,
        },
        "corte": {"profundidad_media_m": 14.0},   # excavacion caja 14m profundidad
        "terraplen": {"altura_media_m": 3.0},       # rampas de acceso h=3m
    }

    # Construir estructura de recintos viales
    viales = [
        {"nombre": r["nombre"], "area_m2": r["area_m2"]}
        for r in resultado["recintos"]
    ]
    cub_partidas = cubicar_vial(viales, secciones=secciones_metro)

    # Resultado mock compatible con cubicar() para pipeline presupuesto
    area_total = sum(r["area_m2"] for r in resultado["recintos"])
    cub = {
        "partidas": cub_partidas,
        "altura_global": 0,
        "recintos_procesados": len(resultado["recintos"]),
        "advertencias": [],
        "resumen_areas": {
            "total_m2": area_total,
            "humedo_m2": 0.0,
            "seco_m2": 0.0,
            "exterior_m2": 0.0,
            "comun_m2": 0.0,
            "vial_m2": area_total,
            "confiable_m2": area_total,
            "incierta_m2": 0.0,
        },
    }

    print(f"\n      Partidas generadas: {len(cub_partidas)}")
    print()
    print(f"{'PARTIDA':<45} {'UNIDAD':>8} {'CANTIDAD':>14}")
    print("-" * 69)
    for p in cub_partidas:
        print(f"  {p['partida']:<43} {p['unidad']:>8} {p['cantidad']:>14,.1f}")
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
    ref_mm = 9_000.0
    diff_pct = (total_mm - ref_mm) / ref_mm * 100
    print()
    print(f"  Presupuesto referencial obras civiles:  ${ref_mm:,.0f} MM CLP")
    print(f"  Nuestra estimacion:                     ${total_mm:,.1f} MM CLP")
    print(f"  Diferencia:                             {diff_pct:+.1f}%")
    if abs(diff_pct) < 30:
        print("  -> Rango razonable para estimacion obras civiles estructurales")
    else:
        print("  -> Fuera de rango — revisar secciones o precios unitarios")
    print()

    print(f"[4/4] Generando Excel -> {args.excel}")
    exportar_excel(resultado, None, cub, pres, Path(args.excel))
    print(f"  [OK] {args.excel}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
