#!/usr/bin/env python3
"""
demo_ruta1.py — cubicacion sintetica Ruta 1 Paso Malo–Caleta Urco

Datos reales de la licitacion MOP Vialidad Antofagasta 2025:
  - 21 km calzada bidireccional
  - Presupuesto referencial: $20.000 millones CLP
  - Obras: pavimento, cunetas, muros contencion, tunel Galleguillos, seguridad vial

Uso:
    python demo_ruta1.py
    python demo_ruta1.py --excel ruta1_cubicacion.xlsx
"""

import argparse
from pathlib import Path

from cubicador import cubicar
from presupuesto import cargar_precios, presupuestar, imprimir_presupuesto
from excel import exportar_excel

# ─── Datos reales del proyecto ────────────────────────────────────────────────
# Fuente: MOP Vialidad Antofagasta, licitacion enero 2025
# Ruta 1: Paso Malo – Caleta Urco, Tocopilla, Region de Antofagasta
# 21 km bidireccional, presupuesto >$20.000 millones CLP

ANCHO_CALZADA_M   = 7.30   # 2 pistas 3.65m c/u (norma MOP via secundaria)
ANCHO_BERMA_M     = 1.00   # berma pavimentada cada lado
LONGITUD_M        = 21_000 # 21 km en metros
ANCHO_CUNETA_M    = 0.60   # cuneta tipo SERVIU revestida

# Tunel Galleguillos (estimado de noticias: "obras en el tunel")
TUNEL_LONGITUD_M  = 180    # estimacion conservadora
TUNEL_ANCHO_M     = 9.0    # tunel bidireccional rural
TUNEL_ALTO_M      = 6.0

# Muros de contencion (tramos con corte en laderas — tipico ruta costera)
MUROS_AREA_M2     = 4_500  # estimacion: ~500m de muro, altura media 9m

# Calzada principal
AREA_CALZADA = LONGITUD_M * (ANCHO_CALZADA_M + 2 * ANCHO_BERMA_M)  # 21km × 9.3m = 195,300 m²

# Cunetas (ambos lados del camino)
AREA_CUNETA  = LONGITUD_M * 2 * ANCHO_CUNETA_M   # 21km × 2 × 0.6m = 25,200 m²

# Tunel (area planta = longitud × ancho)
AREA_TUNEL   = TUNEL_LONGITUD_M * TUNEL_ANCHO_M  # 180 × 9 = 1,620 m²

# Demarcacion vial: marcas termoplasticas (linea centro + bordes) — 21km × 2.4m efectivo
AREA_DEMARCACION = LONGITUD_M * 2.4              # 50,400 m²

# Senaletiva vertical: ~560 senales (1 c/75m cada lado) × 1.5 m²/panel = 840 m²
AREA_SENALES     = 560 * 1.5                     # 840 m²

# Iluminacion vial: poste cada 40m ambos lados = 1,050 postes × 4 m² huella
AREA_ILUMINACION = round(LONGITUD_M / 40 * 2 * 4)  # 4,200 m²

# Terraplenes: 50% de la ruta en seccion de relleno, ancho calzada
AREA_TERRAPLEN   = round(LONGITUD_M * 0.50 * (ANCHO_CALZADA_M + 2 * ANCHO_BERMA_M))  # 97,650 m²

# Alcantarillas transversales: 1 cada 250m = 84 unidades, L=12m, ancho=1.5m
AREA_ALCANTARILLA = round(LONGITUD_M / 250 * 12 * 1.5)  # 1,512 m²

# Guardavias: 20% de la ruta, ambos lados, ancho planta 0.5m
AREA_GUARDAVIA   = round(LONGITUD_M * 0.20 * 2 * 0.5)   # 4,200 m²

# Revegetacion taludes: 30% de la ruta, talud 6m ancho c/lado
AREA_REVEGETACION = round(LONGITUD_M * 0.30 * 6)         # 37,800 m²

# Colector longitudinal PVC: 40% de la ruta, zanja 0.8m ancho
AREA_COLECTOR    = round(LONGITUD_M * 0.40 * 0.8)        # 6,720 m² → 8,400 ml


def construir_resultado() -> dict:
    """
    Construye un dict 'resultado' con la estructura que produce poc_cubicacion.py.
    Representa los elementos extraidos de los planos planta/perfil de la Ruta 1.
    """
    recintos = [
        # Calzada principal (bidireccional, pavimento flexible)
        {
            "nombre": "CALZADA PRINCIPAL",
            "area_m2": round(AREA_CALZADA, 1),
            "confianza": 0.92,
            "departamento": "Ruta 1",
            "dimensiones_estimadas": {"largo_m": LONGITUD_M, "ancho_m": ANCHO_CALZADA_M + 2*ANCHO_BERMA_M},
        },
        # Pista de emergencia / sobre-ancho en curvas (5% de longitud)
        {
            "nombre": "SOBREANCHO CURVAS PISTA",
            "area_m2": round(LONGITUD_M * 0.05 * 2.0, 1),
            "confianza": 0.80,
            "departamento": "Ruta 1",
        },
        # Cunetas revestidas (ambos lados)
        {
            "nombre": "CUNETA REVESTIDA HORMIGON",
            "area_m2": round(AREA_CUNETA, 1),
            "confianza": 0.88,
            "departamento": "Ruta 1",
        },
        # Tunel Galleguillos
        {
            "nombre": "TUNEL GALLEGUILLOS",
            "area_m2": round(AREA_TUNEL, 1),
            "confianza": 0.90,
            "departamento": "Ruta 1",
            "dimensiones_estimadas": {"largo_m": TUNEL_LONGITUD_M, "ancho_m": TUNEL_ANCHO_M},
        },
        # Muros de contencion (varios tramos en laderas)
        {
            "nombre": "MURO DE CONTENCION HORMIGON",
            "area_m2": MUROS_AREA_M2,
            "confianza": 0.85,
            "departamento": "Ruta 1",
        },
        # Miradores (obra civil menor — km 210 y 213): NO son calzada, se excluyen de pavimento
        {
            "nombre": "MIRADOR CALZADA KM210",
            "area_m2": 480.0,
            "confianza": 0.75,
            "departamento": "Ruta 1",
        },
        {
            "nombre": "MIRADOR CALZADA KM213",
            "area_m2": 480.0,
            "confianza": 0.75,
            "departamento": "Ruta 1",
        },
        # Demarcacion y senaletiva
        {
            "nombre": "DEMARCACION VIAL CALZADA",
            "area_m2": float(AREA_DEMARCACION),
            "confianza": 0.90,
            "departamento": "Ruta 1",
        },
        {
            "nombre": "SENALETIVA VERTICAL KM0-KM21",
            "area_m2": float(AREA_SENALES),
            "confianza": 0.85,
            "departamento": "Ruta 1",
        },
        # Equipamiento vial
        {
            "nombre": "ILUMINACION VIAL RUTA 1",
            "area_m2": float(AREA_ILUMINACION),
            "confianza": 0.85,
            "departamento": "Ruta 1",
        },
        {
            "nombre": "GUARDAVIA FLEXIBLE W KM0-KM21",
            "area_m2": float(AREA_GUARDAVIA),
            "confianza": 0.85,
            "departamento": "Ruta 1",
        },
        # Movimiento de tierras
        {
            "nombre": "TERRAPLEN COMPACTADO",
            "area_m2": float(AREA_TERRAPLEN),
            "confianza": 0.80,
            "departamento": "Ruta 1",
        },
        # Drenaje transversal
        {
            "nombre": "ALCANTARILLA MARCO HORMIGON",
            "area_m2": float(AREA_ALCANTARILLA),
            "confianza": 0.82,
            "departamento": "Ruta 1",
        },
        # Obras verdes
        {
            "nombre": "REVEGETACION TALUDES",
            "area_m2": float(AREA_REVEGETACION),
            "confianza": 0.78,
            "departamento": "Ruta 1",
        },
        # Drenaje longitudinal
        {
            "nombre": "COLECTOR PVC DRENAJE LONGITUDINAL",
            "area_m2": float(AREA_COLECTOR),
            "confianza": 0.80,
            "departamento": "Ruta 1",
        },
    ]

    return {
        "pagina":    1,
        "pdf":       "Planos_Ruta1_PasoMalo_CaletaUrco_MOP2025.pdf",
        "recintos":  recintos,
        "muros":     {"exterior_ml": 0, "interior_ml": 0},
        "vanos":     {"puertas": [], "ventanas": []},
        "schedule":  {"tiene_tabla": False},
        "_tokens_entrada":  4200,
        "_tokens_salida":    380,
        "_costo_usd":       0.047,
        "_tiempo_s":        8.3,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo cubicacion Ruta 1 MOP 2025")
    parser.add_argument("--excel", default="ruta1_cubicacion.xlsx",
                        help="Archivo Excel de salida (default: ruta1_cubicacion.xlsx)")
    parser.add_argument("--precios", default="precios_cl.csv",
                        help="CSV de precios (default: precios_cl.csv)")
    parser.add_argument("--gg-utilidad", type=float, default=0.25,
                        help="GG + utilidad (default: 0.25)")
    parser.add_argument("--iva", type=float, default=0.19,
                        help="IVA (default: 0.19)")
    args = parser.parse_args()

    print("=" * 70)
    print("  CUBICACION DEMO — Ruta 1: Paso Malo – Caleta Urco")
    print("  MOP Vialidad Antofagasta | Licitacion enero 2025")
    print(f"  {LONGITUD_M/1000:.0f} km | Presupuesto referencial >$20.000 MM CLP")
    print("=" * 70)

    # 1. Construir resultado sintetico
    resultado = construir_resultado()
    print(f"\n[1/4] Datos: {len(resultado['recintos'])} elementos detectados")
    for r in resultado["recintos"]:
        print(f"      {r['nombre']:<40} {r['area_m2']:>10,.0f} m²")

    # 2. Cubicacion (cantidades por partida)
    sec_custom = {
        "tunel": {
            "ancho_excav_m":          TUNEL_ANCHO_M,
            "alto_excav_m":           TUNEL_ALTO_M,
            "espesor_revestimiento_m": 0.45,
            "kg_acero_por_m3_revest":  85,
        },
        "muro_contencion": {
            "espesor_m":      0.45,
            "kg_acero_por_m3": 90,
        },
        "cuneta":      {"ancho_m": ANCHO_CUNETA_M},
        "terraplen":   {"altura_media_m": 1.80},
        "alcantarilla":{"ancho_interno_m": 1.50},
        "senaletiva":  {"area_m2_por_senal": 1.50},
        "iluminacion": {"m2_por_poste": 4.0},
        "defensa_vial":{"ancho_m": 0.50},
    }

    print("\n[2/4] Cubicando...")
    cubicacion = cubicar(resultado, altura_global=0, secciones=sec_custom)

    print(f"\n      Partidas generadas: {len(cubicacion['partidas'])}")
    print(f"\n{'PARTIDA':<42} {'UNIDAD':>6} {'CANTIDAD':>14}")
    print("-" * 66)
    for p in cubicacion["partidas"]:
        print(f"  {p['partida']:<40} {p['unidad']:>6} {p['cantidad']:>14,.1f}")

    # 3. Presupuesto
    precios_path = Path(args.precios)
    if not precios_path.exists():
        print(f"\n[!] {args.precios} no encontrado — presupuesto omitido")
        presupuesto = None
    else:
        print("\n[3/4] Calculando presupuesto...")
        precios = cargar_precios(precios_path)
        presupuesto = presupuestar(
            cubicacion, precios,
            gg_utilidad=args.gg_utilidad,
            iva=args.iva,
        )
        imprimir_presupuesto(presupuesto)

        # Comparar con presupuesto referencial MOP
        total = presupuesto["subtotales"]["total_con_iva"]
        ref   = 20_000_000_000  # $20.000 millones CLP
        delta = (total - ref) / ref * 100
        print(f"\n  Presupuesto referencial MOP:  ${ref/1e9:.0f}.000 MM CLP")
        print(f"  Nuestra estimacion:           ${total/1e9:.1f} MM CLP")
        print(f"  Diferencia:                   {delta:+.1f}%")
        if abs(delta) < 30:
            print("  → Rango razonable para estimacion preliminar desde planos")
        else:
            print("  → Diferencia alta — revisar secciones en secciones_civiles.yaml")

    # 4. Excel
    print(f"\n[4/4] Generando Excel → {args.excel}")
    exportar_excel(
        resultado=resultado,
        schedule=resultado.get("schedule"),
        cubicacion=cubicacion,
        presupuesto=presupuesto,
        ruta_salida=Path(args.excel),
    )
    print(f"  [OK] {args.excel}")
    print("\nDone.")


if __name__ == "__main__":
    main()
