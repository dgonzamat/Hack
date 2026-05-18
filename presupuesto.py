"""
Presupuesto: multiplica cantidades cubicadas × precios unitarios.

Lee precios desde CSV (default precios_cl.csv) y produce presupuesto en CLP
con desglose por partida + GG&U + IVA.
"""

import csv
from pathlib import Path


def cargar_precios(ruta: str | Path) -> dict[str, dict]:
    """
    Lee CSV de precios y devuelve dict: {partida: {unidad, precio_clp, fuente, fecha}}.
    Ignora lineas que empiezan con #.
    """
    precios = {}
    with open(ruta, encoding="utf-8") as f:
        lineas = [l for l in f if not l.strip().startswith("#") and l.strip()]
    reader = csv.DictReader(lineas)
    for row in reader:
        precios[row["partida"]] = {
            "unidad": row["unidad"],
            "precio_clp": int(row["precio_clp"]),
            "fuente": row.get("fuente", ""),
            "fecha": row.get("fecha", ""),
        }
    return precios


def presupuestar(
    cubicacion: dict,
    precios: dict[str, dict],
    gg_utilidad: float = 0.25,
    iva: float = 0.19,
) -> dict:
    """
    Multiplica cantidades × precios y suma GG&U + IVA.

    Devuelve dict con:
      - lineas: [{partida, descripcion, unidad, cantidad, precio_unitario, subtotal_clp, fuente}]
      - subtotales: {neto, gg_utilidad_monto, con_gg, iva_monto, total_con_iva}
      - faltantes: partidas en cubicacion sin precio definido
    """
    lineas = []
    faltantes = []
    subtotal_neto = 0

    for p in cubicacion.get("partidas", []):
        partida = p["partida"]
        precio_info = precios.get(partida)
        if not precio_info:
            faltantes.append(partida)
            continue
        precio_un = precio_info["precio_clp"]
        cantidad = p["cantidad"]
        subtotal = int(round(precio_un * cantidad))
        subtotal_neto += subtotal
        lineas.append({
            "partida": partida,
            "descripcion": p.get("descripcion", partida),
            "unidad": p["unidad"],
            "cantidad": cantidad,
            "precio_unitario_clp": precio_un,
            "subtotal_clp": subtotal,
            "fuente": precio_info["fuente"],
            "nota": p.get("nota") or p.get("supuesto", ""),
            "tipo": p.get("tipo", "residencial"),
        })

    gg_monto = int(round(subtotal_neto * gg_utilidad))
    con_gg = subtotal_neto + gg_monto
    iva_monto = int(round(con_gg * iva))
    total = con_gg + iva_monto

    return {
        "lineas": lineas,
        "subtotales": {
            "neto": subtotal_neto,
            "gg_utilidad_pct": gg_utilidad,
            "gg_utilidad_monto": gg_monto,
            "con_gg": con_gg,
            "iva_pct": iva,
            "iva_monto": iva_monto,
            "total_con_iva": total,
        },
        "faltantes": faltantes,
    }


def formatear_clp(monto: int) -> str:
    """Formatea entero en CLP con separadores de miles."""
    return f"$ {monto:,}".replace(",", ".")


def imprimir_presupuesto(pres: dict) -> None:
    """Imprime el presupuesto formateado en consola."""
    print()
    print("═" * 76)
    print("  PRESUPUESTO")
    print("═" * 76)
    print(f"  {'PARTIDA':<40} {'CANTIDAD':>12} {'P.UNIT':>10} {'SUBTOTAL':>12}")
    print("─" * 76)
    tipo_actual = None
    for l in pres["lineas"]:
        tipo = l.get("tipo", "residencial")
        if tipo != tipo_actual:
            if tipo == "vial":
                print("─" * 76)
                print("  INFRAESTRUCTURA VIAL (cantidades estimadas — ver supuestos)")
                print("─" * 76)
            tipo_actual = tipo
        cant_str = f"{l['cantidad']:.1f} {l['unidad']}"
        print(
            f"  {l['descripcion'][:40]:<40} "
            f"{cant_str:>12} "
            f"{formatear_clp(l['precio_unitario_clp']):>10} "
            f"{formatear_clp(l['subtotal_clp']):>12}"
        )
    s = pres["subtotales"]
    gg_label = f"GG + Utilidad ({s['gg_utilidad_pct']*100:.0f}%)"
    iva_label = f"IVA ({s['iva_pct']*100:.0f}%)"
    print("─" * 76)
    print(f"  {'SUBTOTAL NETO':<64} {formatear_clp(s['neto']):>12}")
    print(f"  {gg_label:<64} {formatear_clp(s['gg_utilidad_monto']):>12}")
    print(f"  {'SUBTOTAL + GG&U':<64} {formatear_clp(s['con_gg']):>12}")
    print(f"  {iva_label:<64} {formatear_clp(s['iva_monto']):>12}")
    print("─" * 76)
    print(f"  {'TOTAL CON IVA':<64} {formatear_clp(s['total_con_iva']):>12} CLP")
    print("═" * 76)
    if pres.get("faltantes"):
        print(f"\n  ⚠ Partidas sin precio definido: {', '.join(pres['faltantes'])}")
    print()
