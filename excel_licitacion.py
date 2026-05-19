"""
Genera Excel en formato Cuadro de Precios de Licitacion (estructura STM Vitacura).
Toma el template original, pre-llena cantidades calculadas y agrega hoja de analisis.
"""

import math
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# ── UF referencial mayo 2026 ──────────────────────────────────────────────────
UF_CLP = 38_500

# ── Fills ─────────────────────────────────────────────────────────────────────
_FILL_HEADER   = PatternFill("solid", fgColor="1F4E79")   # azul oscuro
_FILL_SECTION  = PatternFill("solid", fgColor="BDD7EE")   # azul claro (sección padre)
_FILL_CALC     = PatternFill("solid", fgColor="E2EFDA")   # verde claro (calculado por nosotros)
_FILL_ORIGINAL = PatternFill("solid", fgColor="FFF2CC")   # amarillo pálido (ya en template)
_FILL_PRICE    = PatternFill("solid", fgColor="FFFF00")   # amarillo (contratista llena precio)
_FILL_WARN     = PatternFill("solid", fgColor="FCE4D6")   # salmón (no cubicado)

_FONT_HEADER = Font(bold=True, color="FFFFFF", size=10)
_FONT_BOLD   = Font(bold=True, size=9)
_FONT_NORM   = Font(size=9)

_BORDER_THIN = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"),  bottom=Side(style="thin"),
)


def _cell(ws, row: int, col: int, value=None, fill=None, font=None,
          alignment=None, number_format=None):
    c = ws.cell(row=row, column=col, value=value)
    if fill:       c.fill = fill
    if font:       c.font = font
    if alignment:  c.alignment = alignment
    if number_format: c.number_format = number_format
    c.border = _BORDER_THIN
    return c


# ── Mapeo: clave de cubicacion → ítems de licitacion (por pique y tunel) ──────
# Para PIQUE N (1..9): reemplazar {p} por el número
_PIQUE_ITEMS = {
    "excavacion_pique":            "4.{p}.1",
    "retiro_excavacion_pique":     "4.{p}.2",
    "montaje_liner_pique":         "4.{p}.3",
    "montaje_escalas_plataformas": "4.{p}.8",
    # brocal_definitivo: piques 1,9 tienen 15 sub-ítems (→ .15); piques 2-8 tienen 14 (→ .14)
    # Se maneja dinámicamente en _build_qty_map
}
# Items de tunnel: para tramo T (1..8)
_TUNEL_ITEMS = {
    "excavacion_tunel":        "5.{t}.1",
    "retiro_excavacion_tunel": "5.{t}.2",
    "montaje_liner_tunel":     "5.{t}.3",
    "radier_tunel":            "5.{t}.7",
}
# Piques 1,9 tienen ítem extra "Montaje estructura soporte de cables" (4.x.13)
# → brocal definitivo queda en 4.x.15. Para piques 2-8 está en 4.x.14.
_BROCAL_NUM: dict[int, str] = {p: "14" for p in range(2, 9)}
_BROCAL_NUM.update({1: "15", 9: "15"})


def _build_qty_map(cubicacion: dict) -> dict[str, float]:
    """
    Construye {item_num: cantidad} a partir de las partidas cubicadas.

    Si cubicacion tiene piques_qty / tramos_qty (modo multi-pique estructurado),
    genera una entrada por pique (4.1.x … 4.9.x) y por tramo (5.1.x … 5.8.x).
    Fallback: PIQUE 1 solamente y distribución uniforme entre 8 tramos.
    """
    qty: dict[str, float] = {}

    piques_qty: dict = cubicacion.get("piques_qty", {})
    tramos_qty: dict = cubicacion.get("tramos_qty", {})

    if piques_qty:
        for pid, pq in piques_qty.items():
            pid_i = int(pid)
            for key, tpl in _PIQUE_ITEMS.items():
                if key in pq:
                    qty[tpl.replace("{p}", str(pid_i))] = pq[key]
            if "brocal_definitivo" in pq:
                brocal_num = _BROCAL_NUM.get(pid_i, "15")
                qty[f"4.{pid_i}.{brocal_num}"] = pq["brocal_definitivo"]
    else:
        partidas = {p["partida"]: p["cantidad"] for p in cubicacion.get("partidas", [])}
        for key, tpl in _PIQUE_ITEMS.items():
            if key in partidas:
                qty[tpl.replace("{p}", "1")] = partidas[key]
        if "brocal_definitivo" in partidas:
            qty["4.1.15"] = partidas["brocal_definitivo"]

    if tramos_qty:
        for tid, tq in tramos_qty.items():
            for key, tpl in _TUNEL_ITEMS.items():
                if key in tq:
                    num = tpl.replace("{t}", str(tid))
                    qty[num] = tq[key]
    else:
        partidas = {p["partida"]: p["cantidad"] for p in cubicacion.get("partidas", [])}
        n_tramos = 8
        for key, tpl in _TUNEL_ITEMS.items():
            if key in partidas:
                cant_por_tramo = round(partidas[key] / n_tramos, 3)
                for t in range(1, n_tramos + 1):
                    qty[tpl.replace("{t}", str(t))] = cant_por_tramo

    return qty


def _fill_detalle_sheet(ws, qty_map: dict[str, float]) -> dict[str, int]:
    """
    Recorre la hoja 'A) Detalle Costo Directo', aplica colores y fórmulas.
    Devuelve {item_num: row_index} para referencia.
    """
    item_rows: dict[str, int] = {}
    wrap = Alignment(wrap_text=True, vertical="top")

    for row in ws.iter_rows():
        num_cell = row[0]
        num = str(num_cell.value).strip() if num_cell.value else ""
        if not num:
            continue

        row_idx = num_cell.row
        item_rows[num] = row_idx

        # Sección padre (1.0, 2.0, 3.0, ...)
        is_parent = num.endswith(".0") or (num.count(".") == 0 and num.isdigit())
        if is_parent:
            for c in row:
                if c.value is not None:
                    c.font = _FONT_BOLD
                    c.fill = _FILL_SECTION
            continue

        qty_cell  = ws.cell(row=row_idx, column=4)   # D
        price_cell = ws.cell(row=row_idx, column=5)  # E
        total_cell = ws.cell(row=row_idx, column=6)  # F

        # Precio: siempre amarillo (contractor fills)
        price_cell.fill = _FILL_PRICE
        price_cell.font = _FONT_NORM

        # Cantidad: calculada por nosotros o ya estaba en el template
        if num in qty_map:
            qty_cell.value = round(qty_map[num], 2)
            qty_cell.fill = _FILL_CALC
            qty_cell.font = _FONT_NORM
            qty_cell.number_format = "#,##0.00"
            total_cell.value = f"=D{row_idx}*E{row_idx}"
            total_cell.number_format = "#,##0.00"
        elif qty_cell.value is not None and qty_cell.value != 0:
            qty_cell.fill = _FILL_ORIGINAL
            qty_cell.font = _FONT_NORM
            total_cell.value = f"=D{row_idx}*E{row_idx}"
            total_cell.number_format = "#,##0.00"

        # Descripcion: wrap text
        desc_cell = ws.cell(row=row_idx, column=2)
        desc_cell.alignment = wrap

    # Ajustar anchos de columna
    ws.column_dimensions["A"].width = 9
    ws.column_dimensions["B"].width = 55
    ws.column_dimensions["C"].width = 8
    ws.column_dimensions["D"].width = 13
    ws.column_dimensions["E"].width = 16
    ws.column_dimensions["F"].width = 14
    ws.column_dimensions["G"].width = 22
    ws.column_dimensions["H"].width = 30

    return item_rows


# ── Hoja Análisis de Precios ──────────────────────────────────────────────────

_BENCHMARKS = [
    # (partida, unidad, uf_min, uf_max, referencia)
    ("Excavación pique Ø4m",            "m³",  2.0,  3.5,  "ONDAC 2026"),
    ("Retiro excavación pique",          "m³",  0.8,  1.5,  "Mercado Santiago"),
    ("Montaje liner pique Ø4m (solo inst.)", "m",  4.0,  8.0,  "Est. mercado"),
    ("Shotcrete en pique",               "m³",  4.5,  7.0,  "ONDAC 2026"),
    ("Malla electrosoldada",             "kg",  0.03, 0.05, "ONDAC 2026"),
    ("Montaje escalas+plataformas",      "gl",  60,   120,  "Est. mercado/pique"),
    ("Brocal definitivo",                "gl",  80,   150,  "Est. mercado"),
    ("Excavación túnel Ø2.21m",          "m³",  3.5,  6.0,  "ONDAC 2026 tunel urbano"),
    ("Montaje liner túnel Ø2.21m",       "m",   3.5,  6.0,  "Est. instalación"),
    ("Radier túnel H30",                 "m³",  7.0,  10.0, "ONDAC 2026"),
]

_NO_CUBICADO = [
    ("4.x.10  Shotcrete", "m³",  "Depende de clasificación RMR del terreno (geotecnia)"),
    ("4.x.11  Malla",     "kg",  "Diseño geotécnico — varía según tipo de suelo"),
    ("4.x.12  Pernos de convergencia", "und", "Análisis convergencia-confinamiento requerido"),
    ("4.x.4   Refuerzo Losa Anillo Fondo", "gl", "Suma alzada — cotización directa contratista"),
    ("4.x.5   Construcción Dren",     "gl",  "Suma alzada — cotización directa contratista"),
    ("4.x.6   Terminaciones",         "gl",  "Suma alzada — cotización directa contratista"),
    ("4.x.7   Cobertura pique",       "gl",  "Suma alzada — cotización directa contratista"),
    ("4.x.9   Refuerzo apertura",     "gl",  "Suma alzada — cotización directa contratista"),
    ("4.x.14  Brocal temporal",       "gl",  "Suma alzada — cotización directa contratista"),
    ("Sec. 2  Suministros (liner, fans, escalas)", "—",
     "Aporte STM: mandante suministra, contratista solo instala"),
    ("Sec. 1  Actividades Previas y Coordinación", "gl", "Suma alzada — depende de empresa"),
    ("Sec. 3  Instalación de Faenas", "gl",  "Suma alzada — depende de empresa"),
]

# Cantidades pique 1 para escenarios
_PIQUE1_ESCENARIOS = [
    ("Excavación pique",            251.4, 2.0,  2.75, 3.5),
    ("Retiro excavación",           251.4, 0.8,  1.15, 1.5),
    ("Montaje liner pique",          20.0, 4.0,  6.0,  8.0),
    ("Montaje escalas+plataformas",   1.0, 60.0, 90.0, 120.0),
    ("Brocal definitivo",             1.0, 80.0, 115.0, 150.0),
]


def _build_analisis_sheet(wb: openpyxl.Workbook, cubicacion: dict) -> None:
    ws = wb.create_sheet("Análisis de Precios")
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 14
    ws.column_dimensions["E"].width = 14
    ws.column_dimensions["F"].width = 35

    wrap = Alignment(wrap_text=True, vertical="top")
    ctr  = Alignment(horizontal="center", vertical="center")
    right = Alignment(horizontal="right", vertical="center")

    row = 1

    def title(text, r=None):
        nonlocal row
        r = r or row
        c = ws.cell(row=r, column=1, value=text)
        c.font = _FONT_HEADER
        c.fill = _FILL_HEADER
        c.alignment = ctr
        ws.merge_cells(f"A{r}:F{r}")
        row = r + 1

    def subtitle(text):
        nonlocal row
        c = ws.cell(row=row, column=1, value=text)
        c.font = _FONT_BOLD
        c.fill = _FILL_SECTION
        ws.merge_cells(f"A{row}:F{row}")
        row += 1

    def header_row(cols):
        nonlocal row
        for i, h in enumerate(cols, 1):
            c = ws.cell(row=row, column=i, value=h)
            c.font = _FONT_BOLD
            c.fill = _FILL_SECTION
            c.alignment = ctr
            c.border = _BORDER_THIN
        row += 1

    def data_row(cols, fill=None):
        nonlocal row
        for i, v in enumerate(cols, 1):
            c = ws.cell(row=row, column=i, value=v)
            c.font = _FONT_NORM
            c.alignment = wrap
            c.border = _BORDER_THIN
            if fill:
                c.fill = fill
        row += 1

    def blank():
        nonlocal row
        row += 1

    # ── Encabezado ────────────────────────────────────────────────────────────
    title("ANÁLISIS DE PRECIOS — TÚNEL LAT VITACURA-PROVIDENCIA")
    ws.cell(row=row, column=1,
            value=f"UF referencial: {UF_CLP:,} CLP (mayo 2026) | Generado: {__import__('datetime').date.today()}")
    ws.merge_cells(f"A{row}:F{row}")
    ws.cell(row=row, column=1).font = Font(italic=True, size=8)
    row += 1
    blank()

    # ── Sección 1: Cubicación realizada ───────────────────────────────────────
    subtitle("1. CUBICACIÓN REALIZADA (cantidades pre-llenadas en hoja A)")
    header_row(["Partida", "Cant.", "Unidad", "Ítems licitación", "UF est. medio", "Fuente / Cómo se calculó"])

    partidas_map = {p["partida"]: p for p in cubicacion.get("partidas", [])}
    cubiertos = [
        ("Excavación pique",            "excavacion_pique",            "4.1.1",  2.75,  "área(12.57m²) × profundidad(20m)"),
        ("Retiro excavación",           "retiro_excavacion_pique",     "4.1.2",  1.15,  "igual excavación — flete botadero"),
        ("Montaje liner pique",         "montaje_liner_pique",         "4.1.3",  6.0,   "profundidad pique (20m = 20 anillos)"),
        ("Montaje escalas+plataformas", "montaje_escalas_plataformas", "4.1.8",  90.0,  "1 gl por pique (STM aporta estructuras)"),
        ("Brocal definitivo",           "brocal_definitivo",           "4.1.15", 115.0, "1 gl por pique"),
        ("Excavación túnel",            "excavacion_tunel",            "5.1-5.8",5.0,   "área(3.84m²) × longitud / 8 tramos"),
        ("Montaje liner túnel Ø2.21m",  "montaje_liner_tunel",         "5.1-5.8",4.75,  "longitud tunel / 8 tramos"),
        ("Radier túnel H30",            "radier_tunel",                "5.1-5.8",8.5,   "área × espesor(0.15m)"),
    ]
    for desc, key, items, uf_med, fuente in cubiertos:
        p = partidas_map.get(key)
        if p:
            uf_total = round(p["cantidad"] * uf_med, 1)
            data_row([desc, round(p["cantidad"], 2), p.get("unidad", ""), items,
                      f"{uf_total:,.0f} UF", fuente], fill=_FILL_CALC)
    blank()

    # ── Sección 2: No cubicado ────────────────────────────────────────────────
    subtitle("2. NO CUBICADO — Requiere estudio específico o suma alzada del contratista")
    header_row(["Ítem licitación", "Unidad", "Razón / Recomendación", "", "", ""])
    ws.merge_cells(f"C{row-1}:F{row-1}")
    for item, unidad, razon in _NO_CUBICADO:
        c1 = ws.cell(row=row, column=1, value=item)
        c1.font = _FONT_NORM; c1.border = _BORDER_THIN; c1.fill = _FILL_WARN
        c2 = ws.cell(row=row, column=2, value=unidad)
        c2.font = _FONT_NORM; c2.border = _BORDER_THIN; c2.fill = _FILL_WARN
        c3 = ws.cell(row=row, column=3, value=razon)
        c3.font = Font(italic=True, size=9); c3.border = _BORDER_THIN
        c3.alignment = wrap
        ws.merge_cells(f"C{row}:F{row}")
        row += 1
    blank()

    # ── Sección 3: Benchmarks mercado ─────────────────────────────────────────
    subtitle("3. PRECIOS DE REFERENCIA MERCADO CHILE 2026 (estimados — solicitar cotización formal)")
    header_row(["Partida", "Unidad", "UF mín/un", "UF máx/un",
                "CLP mín/un (aprox)", "Referencia"])
    for desc, unidad, uf_min, uf_max, ref in _BENCHMARKS:
        data_row([
            desc, unidad,
            f"{uf_min:.2f}", f"{uf_max:.2f}",
            f"${int(uf_min*UF_CLP):,} – ${int(uf_max*UF_CLP):,}",
            ref,
        ])
    blank()

    # ── Sección 4: Análisis de sensatez — proyecto completo ─────────────────
    piques_qty = cubicacion.get("piques_qty", {})
    tramos_qty = cubicacion.get("tramos_qty", {})

    # Construir escenarios desde datos reales si están disponibles
    if piques_qty and tramos_qty:
        total_excav_pq = sum(pq["excavacion_pique"] for pq in piques_qty.values())
        total_liner_pq = sum(pq["montaje_liner_pique"] for pq in piques_qty.values())
        total_escalas  = len(piques_qty)
        total_brocal   = len(piques_qty)
        total_excav_tn = sum(tq["excavacion_tunel"] for tq in tramos_qty.values())
        total_liner_tn = sum(tq["montaje_liner_tunel"] for tq in tramos_qty.values())
        total_radier   = sum(tq["radier_tunel"] for tq in tramos_qty.values())
        n_piques = len(piques_qty)
        n_tramos = len(tramos_qty)
        subtitle(f"4. ANÁLISIS DE SENSATEZ — PROYECTO COMPLETO ({n_piques} piques + {n_tramos} tramos)")
        escenarios = [
            ("Excavación piques",          total_excav_pq, 2.0,  2.75, 3.5),
            ("Retiro excav. piques",       total_excav_pq, 0.8,  1.15, 1.5),
            ("Montaje liner piques",       total_liner_pq, 4.0,  6.0,  8.0),
            ("Montaje escalas+plataformas",total_escalas,  60.0, 90.0, 120.0),
            ("Brocal definitivo",          total_brocal,   80.0, 115.0,150.0),
            ("Excavación túnel",           total_excav_tn, 3.5,  5.0,  6.0),
            ("Montaje liner túnel",        total_liner_tn, 3.5,  4.75, 6.0),
            ("Radier H30",                 total_radier,   7.0,  8.5,  10.0),
        ]
    else:
        subtitle("4. ANÁLISIS DE SENSATEZ — PIQUE 1 (20m prof., Ø4.0m)")
        escenarios = _PIQUE1_ESCENARIOS

    header_row(["Partida", "Cant.", "UF/un Mín", "UF/un Máx",
                "Subtotal Mín (UF)", "Subtotal Máx (UF)"])

    total_min = total_max = 0.0
    for entry in escenarios:
        desc, cant, uf_min, _mid, uf_max = entry
        sub_min = round(cant * uf_min, 1)
        sub_max = round(cant * uf_max, 1)
        total_min += sub_min
        total_max += sub_max
        data_row([desc, round(cant, 1), f"{uf_min:.2f}", f"{uf_max:.2f}",
                  f"{sub_min:,.1f}", f"{sub_max:,.1f}"])

    for i, v in enumerate([
        "TOTAL ÍTEMS CUBICADOS", "", "", "",
        f"{total_min:,.0f} UF  (~${int(total_min*UF_CLP/1e6):.0f}M CLP)",
        f"{total_max:,.0f} UF  (~${int(total_max*UF_CLP/1e6):.0f}M CLP)",
    ], 1):
        c = ws.cell(row=row, column=i, value=v)
        c.font = _FONT_BOLD; c.fill = _FILL_SECTION; c.border = _BORDER_THIN
    row += 1

    c = ws.cell(row=row, column=1,
        value="⚠ NOTA: El rango anterior NO incluye shotcrete, malla, pernos, terminaciones, "
              "instalación de faenas ni actividades previas (Sec. 1, 3) — típicamente +30-50% adicional.")
    c.font = Font(italic=True, size=8, color="C00000")
    ws.merge_cells(f"A{row}:F{row}")
    row += 2

    # ── Sección 5: Cantidades ya en el template original ──────────────────────
    subtitle("5. CANTIDADES PRE-EXISTENTES EN TEMPLATE (de la licitación original)")
    header_row(["Ítem", "Descripción", "Unidad", "Cantidad original", "", "Fuente"])
    ws.merge_cells(f"E{row-1}:E{row-1}")

    originales = [
        ("5.1.4", "Pernos frente fibra vidrio 4m (eventual)", "und", 39.54),
        ("5.1.5", "Shotcrete frente (eventual)",               "m³",  19.77),
        ("5.1.6", "Paraguas micropilotes (eventual)",          "und", 24),
        ("5.2.4–5.8.4", "Pernos frente (tramos 2-8)",         "und", "36-36 por tramo"),
        ("7.1",  "Base binder asfalto",                        "m²",  317.61),
        ("7.2",  "Base chancada CBR80",                        "m³",  66.70),
        ("7.3",  "Calzada con tratamiento asfaltico",          "m²",  317.61),
        ("7.5",  "Excavación dura y transporte botadero",      "m³",  343.02),
        ("7.10", "Entibación excavaciones",                    "m",   90.75),
        ("7.11", "Reposición áreas verdes",                    "m²",  60),
        ("7.12", "Reposición soleras",                         "m",   40),
        ("7.13", "Demolición y reposición veredas",            "m²",  20),
        ("13.2", "Retiro y transporte aguas efluentes",        "m³",  1000),
    ]
    for item, desc, unid, cant in originales:
        c1 = ws.cell(row=row, column=1, value=item)
        c2 = ws.cell(row=row, column=2, value=desc)
        c3 = ws.cell(row=row, column=3, value=unid)
        c4 = ws.cell(row=row, column=4, value=cant)
        c5 = ws.cell(row=row, column=6, value="Cuadro precios STM rev.1 06/04/2026")
        for c in [c1, c2, c3, c4, c5]:
            c.font = _FONT_NORM; c.border = _BORDER_THIN; c.fill = _FILL_ORIGINAL
        ws.merge_cells(f"E{row}:E{row}")
        row += 1


# ── Función principal ─────────────────────────────────────────────────────────

_TEMPLATE = Path(
    "/root/.claude/uploads/d310c843-729c-4f06-9a18-627b069f8a5a"
    "/207f8ccf-Cuadro_de_Precios_Construcci_n_OOCC_LAT2_0_20260410.xlsx"
)


def exportar_licitacion(
    cubicacion: dict,
    resultado: dict,
    ruta_out: str | Path,
    template: str | Path = _TEMPLATE,
) -> Path:
    """
    Genera Excel en formato licitación STM con cantidades pre-calculadas.
    Devuelve Path del archivo generado.
    """
    ruta_out = Path(ruta_out)

    if Path(template).exists():
        wb = openpyxl.load_workbook(template)
    else:
        # Sin template: crear workbook mínimo
        wb = openpyxl.Workbook()
        wb.active.title = "Resumen Oferta"
        wb.create_sheet("A) Detalle Costo Directo")
        wb.create_sheet("B) Detalle C. Ind., GG y Utilid")

    qty_map = _build_qty_map(cubicacion)

    ws_det = wb["A) Detalle Costo Directo"]
    _fill_detalle_sheet(ws_det, qty_map)

    _build_analisis_sheet(wb, cubicacion)

    wb.save(ruta_out)
    return ruta_out
