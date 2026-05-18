"""
Cubicador: convierte recintos extraidos + muros + vanos en cantidades por partida.

Entrada: el dict del JSON producido por poc_cubicacion.py (v4 o v5)
Salida: lista de partidas con cantidad, unidad y desglose por recinto.
"""

import math
import pickle
import re
from pathlib import Path
from typing import Optional

# ─── Clasificacion de recintos ────────────────────────────────────────────────

_HUMEDOS = re.compile(r"\b(BAÑO|BANO|COCINA|LOGIA|LAVANDER|WC|TOILET)\b")
_SECOS = re.compile(
    r"\b(DORM|DORMITORIO|LIVING|COMEDOR|ESTAR|WALK|CLOSET|VESTIDOR|OFICINA|ESCRITORIO|SALA)\b"
)
_EXTERIORES = re.compile(r"\b(TERRAZA|BALCON|PATIO|JARDIN)\b")
_COMUNES = re.compile(
    r"\b(HALL|PASILLO|CORREDOR|ESCALERA|ASCENSOR|DUCTO|SHAFT|RECEP|CIRCULACION)\b"
)
_VIALES = re.compile(
    r"\b(CALZADA|PISTA|VEREDA|TUNEL|TUNEL|PORTAL|CUNETA|PUENTE|ROTONDA|VIADUCTO|BERMA|CARRIL)\b"
)

# Umbral de probabilidad bajo el cual se marca fue_heuristica=True
_CONFIANZA_ML_MIN = 0.40

_PKL_PATH = Path(__file__).parent / "clasificador_recintos.pkl"
_clf_cache: object = None
_clf_intentado = False


def _cargar_modelo() -> object | None:
    global _clf_cache, _clf_intentado
    if _clf_intentado:
        return _clf_cache
    _clf_intentado = True
    if _PKL_PATH.exists():
        try:
            with open(_PKL_PATH, "rb") as f:
                _clf_cache = pickle.load(f)
        except Exception:
            pass
    return _clf_cache


def _norm(s: str) -> str:
    """Normaliza nombre: mayusculas, sin guiones/barras, sin espacios extra. Mantiene puntos."""
    return re.sub(r"\s+", " ", s.upper().replace("-", " ").replace("/", " ")).strip()


def clasificar_recinto(nombre: str) -> tuple[str, bool]:
    """
    Clasifica un recinto por su nombre. Devuelve (categoria, fue_heuristica).
    Categorias: 'humedo' | 'seco' | 'exterior' | 'comun'
    fue_heuristica=True si la confianza del modelo es baja (<40%) o se usó fallback regex.

    Estrategia: ML (TF-IDF + LR) con fallback a regex si pkl no disponible.
    """
    n = _norm(nombre)
    modelo = _cargar_modelo()
    if modelo is not None:
        pred = modelo.predict([n])[0]
        proba = float(modelo.predict_proba([n]).max())
        return pred, proba < _CONFIANZA_ML_MIN

    # Fallback regex (cuando no hay pkl)
    if _HUMEDOS.search(n):
        return "humedo", False
    if _EXTERIORES.search(n):
        return "exterior", False
    if _COMUNES.search(n):
        return "comun", False
    if _VIALES.search(n):
        return "vial", False
    if _SECOS.search(n):
        return "seco", False
    return "seco", True


# ─── Estimacion de geometria ──────────────────────────────────────────────────

def perimetro_recinto(rec: dict) -> tuple[float, bool]:
    """
    Calcula perimetro de un recinto en metros lineales.
    Si tiene dimensiones_estimadas {largo_m, ancho_m} → usa esas.
    Si solo tiene area_m2 → fallback rectangulo 1.5:1
    Devuelve (perimetro_ml, fue_estimado).
    """
    dim = rec.get("dimensiones_estimadas")
    if dim and dim.get("largo_m") and dim.get("ancho_m"):
        return 2 * (dim["largo_m"] + dim["ancho_m"]), False

    area = rec.get("area_m2")
    if area is None or area <= 0:
        return 0.0, True

    # Fallback rectangulo 1.5:1 — L=sqrt(1.5*A), W=sqrt(A/1.5)
    L = math.sqrt(1.5 * area)
    W = math.sqrt(area / 1.5)
    return 2 * (L + W), True


def area_efectiva(rec: dict) -> Optional[float]:
    """
    Devuelve el area en m² del recinto. Si no tiene area_m2 pero tiene
    dimensiones_estimadas, calcula area = L × W. Si tampoco hay nada, None.
    """
    area = rec.get("area_m2")
    if area is not None and area > 0:
        return float(area)
    dim = rec.get("dimensiones_estimadas")
    if dim and dim.get("largo_m") and dim.get("ancho_m"):
        return float(dim["largo_m"]) * float(dim["ancho_m"])
    return None


# ─── Dimensiones de vanos ─────────────────────────────────────────────────────

# Patrones regex sobre tipo.lower() → (ancho_m, alto_m)
DIMENSIONES_VANOS_DEFAULT = [
    (re.compile(r"puerta.*(doble|150)"), (1.50, 2.10)),
    (re.compile(r"puerta.*(acceso|principal|entrada)"), (0.90, 2.10)),
    (re.compile(r"puerta.*(simple|90|estandar)"), (0.90, 2.00)),
    (re.compile(r"ventana.*(corredera|120)"), (1.20, 1.00)),
    (re.compile(r"ventana.*(fija|paño)"), (1.50, 1.20)),
    (re.compile(r"ventana"), (1.20, 1.00)),
    (re.compile(r"puerta"), (0.90, 2.00)),
]

VANO_DEFAULT = (1.00, 1.50)  # ancho, alto si no matchea nada


def dim_vano(tipo: str) -> tuple[float, float, bool]:
    """Devuelve (ancho_m, alto_m, fue_default) para un tipo de vano."""
    t = (tipo or "").lower()
    for patron, (a, h) in DIMENSIONES_VANOS_DEFAULT:
        if patron.search(t):
            return a, h, False
    return VANO_DEFAULT[0], VANO_DEFAULT[1], True


def area_vanos_total(vanos: dict) -> tuple[float, list[dict]]:
    """
    Suma el area total de puertas + ventanas y devuelve detalle de cada tipo.
    Detalle incluye flag dimension_estimada para trazabilidad.
    """
    detalle = []
    total = 0.0
    for grupo, items in (("puerta", vanos.get("puertas", [])), ("ventana", vanos.get("ventanas", []))):
        for v in items:
            tipo = v.get("tipo", grupo)
            cant = v.get("cantidad", 1) or 1
            ancho, alto, default = dim_vano(tipo)
            area_un = ancho * alto
            total += area_un * cant
            detalle.append({
                "grupo": grupo,
                "tipo": tipo,
                "cantidad": cant,
                "ancho_m": ancho,
                "alto_m": alto,
                "area_unitaria_m2": round(area_un, 2),
                "area_total_m2": round(area_un * cant, 2),
                "dimension_estimada": default,
            })
    return total, detalle


# ─── Altura por recinto ───────────────────────────────────────────────────────

def altura_recinto(rec: dict, altura_global: float, alturas_override: dict[str, float]) -> float:
    """Altura piso-cielo segun nombre. alturas_override: {keyword_upper: altura_m}."""
    n = _norm(rec.get("nombre", ""))
    for kw, h in alturas_override.items():
        if kw.upper() in n:
            return float(h)
    return float(altura_global)


# ─── Cubicacion ───────────────────────────────────────────────────────────────

def cubicar(
    resultado: dict,
    altura_global: float = 2.4,
    alturas_override: Optional[dict[str, float]] = None,
    incluir_comunes: bool = False,
) -> dict:
    """
    Convierte un resultado del PoC (un elemento de 'resultados[]') en cantidades por partida.

    Devuelve dict con:
      - partidas: [{partida, unidad, cantidad, desglose, ...}]
      - clasificacion_recintos: [{nombre, categoria, area, perimetro, fue_heuristica}]
      - vanos_detalle: detalle por tipo de vano con dimensiones aplicadas
      - recintos_sin_area: lista de recintos omitidos
      - resumen_areas: {confiable_m2, incierta_m2, total_m2}
    """
    alturas_override = alturas_override or {}
    recintos = resultado.get("recintos", [])
    muros = resultado.get("muros", {}) or {}
    vanos = resultado.get("vanos", {}) or {}

    # Clasificar y calcular geometria por recinto
    clasif = []
    pintura_int = 0.0
    cielo_m2 = 0.0
    piso_humedo = 0.0
    piso_seco = 0.0
    area_confiable = 0.0
    area_incierta = 0.0
    recintos_sin_area = []
    comunes_omitidos = []
    viales_detectados = []  # infraestructura civil — no entra a cubicación residencial

    # Area total de vanos (asumimos uniforme entre recintos para descuento)
    area_vanos, vanos_detalle = area_vanos_total(vanos)
    n_recs_con_pintura = 0

    for rec in recintos:
        nombre = rec.get("nombre", "?")
        cat, heuristica = clasificar_recinto(nombre)
        area = area_efectiva(rec)
        perim, perim_est = perimetro_recinto(rec)
        h = altura_recinto(rec, altura_global, alturas_override)
        conf = rec.get("confianza") or 0

        info = {
            "nombre": nombre,
            "departamento": rec.get("departamento"),
            "categoria": cat,
            "area_m2": area,
            "perimetro_ml": round(perim, 2),
            "altura_m": h,
            "perim_estimado": perim_est,
            "clasificacion_heuristica": heuristica,
            "confianza": conf,
        }
        clasif.append(info)

        if area is None:
            recintos_sin_area.append(nombre)
            continue

        # Categorizar para confianza
        if conf >= 0.70:
            area_confiable += area
        else:
            area_incierta += area

        # Infraestructura civil: no entra a cubicacion residencial
        if cat == "vial":
            viales_detectados.append({"nombre": nombre, "area_m2": area})
            continue

        # Areas comunes y exteriores no entran a cubicacion default
        if cat == "comun" and not incluir_comunes:
            comunes_omitidos.append({"nombre": nombre, "area_m2": area})
            continue
        if cat == "exterior":
            continue  # terrazas no llevan piso/cielo/pintura interior

        # Pintura interior: perimetro × altura × 2 manos − vanos prorrateados
        if perim > 0:
            pintura_int += perim * h
            n_recs_con_pintura += 1

        # Cielo
        cielo_m2 += area

        # Piso por categoria
        if cat == "humedo":
            piso_humedo += area
        elif cat == "seco":
            piso_seco += area

    # Descontar vanos al area total de pintura (prorrateo simple)
    pintura_int_neta = max(0.0, pintura_int - area_vanos)
    pintura_int_total = pintura_int_neta * 2  # 2 manos

    # Pintura exterior
    ext_ml = muros.get("exterior_ml") or 0
    # Asumir ~30% del area de vanos son exteriores (heuristica)
    area_vanos_ext = area_vanos * 0.3
    pintura_ext_neta = max(0.0, ext_ml * altura_global - area_vanos_ext)
    pintura_ext_total = pintura_ext_neta * 2  # 2 manos

    # Tabiqueria interior
    int_ml = muros.get("interior_ml") or 0
    tabique = int_ml * altura_global

    # Conteos de vanos
    puertas_total = sum((v.get("cantidad", 0) or 0) for v in vanos.get("puertas", []))
    ventanas_area = sum(
        v["area_total_m2"] for v in vanos_detalle if v["grupo"] == "ventana"
    )

    # Armar lista de partidas
    partidas = []

    if pintura_int_total > 0:
        partidas.append({
            "partida": "pintura_interior_latex_2manos",
            "descripcion": "Pintura interior latex 2 manos",
            "unidad": "m2",
            "cantidad": round(pintura_int_total, 1),
            "nota": "perim_recintos × altura − area_vanos (descuento prorrateado)",
        })
    if pintura_ext_total > 0:
        partidas.append({
            "partida": "pintura_exterior_latex_2manos",
            "descripcion": "Pintura exterior latex 2 manos",
            "unidad": "m2",
            "cantidad": round(pintura_ext_total, 1),
            "nota": "muros.exterior_ml × altura − vanos exteriores",
        })
    if cielo_m2 > 0:
        partidas.append({
            "partida": "cielo_volcanita_pintado",
            "descripcion": "Cielo volcanita pintado",
            "unidad": "m2",
            "cantidad": round(cielo_m2, 1),
            "nota": "suma de area de recintos interiores",
        })
    if piso_humedo > 0:
        partidas.append({
            "partida": "piso_ceramico_60x60_instalado",
            "descripcion": "Piso ceramico 60x60 zonas humedas",
            "unidad": "m2",
            "cantidad": round(piso_humedo, 1),
            "nota": "BAÑO + COCINA + LOGIA",
        })
    if piso_seco > 0:
        partidas.append({
            "partida": "piso_flotante_8mm_instalado",
            "descripcion": "Piso flotante 8mm zonas secas",
            "unidad": "m2",
            "cantidad": round(piso_seco, 1),
            "nota": "DORM + LIVING + COMEDOR + WALK-IN",
        })
    if tabique > 0:
        partidas.append({
            "partida": "tabique_volcanita_doble_cara",
            "descripcion": "Tabiqueria volcanita doble cara",
            "unidad": "m2",
            "cantidad": round(tabique, 1),
            "nota": "muros.interior_ml × altura",
        })

    # Puertas: separar por tipo simple/doble si es identificable
    if puertas_total > 0:
        # Si todas son simples (default), una sola partida
        partidas.append({
            "partida": "puerta_simple_90cm_instalada",
            "descripcion": "Puerta simple 90cm instalada",
            "unidad": "un",
            "cantidad": puertas_total,
            "nota": "conteo total de puertas detectadas",
        })

    if ventanas_area > 0:
        partidas.append({
            "partida": "ventana_corredera_aluminio",
            "descripcion": "Ventana corredera aluminio",
            "unidad": "m2",
            "cantidad": round(ventanas_area, 1),
            "nota": "area unitaria × cantidad por tipo",
        })

    return {
        "partidas": partidas,
        "clasificacion_recintos": clasif,
        "vanos_detalle": vanos_detalle,
        "recintos_sin_area": recintos_sin_area,
        "comunes_omitidos": comunes_omitidos,
        "viales_detectados": viales_detectados,
        "resumen_areas": {
            "confiable_m2": round(area_confiable, 1),
            "incierta_m2": round(area_incierta, 1),
            "total_m2": round(area_confiable + area_incierta, 1),
        },
        "config": {
            "altura_global": altura_global,
            "alturas_override": alturas_override,
            "incluir_comunes": incluir_comunes,
        },
    }


# ─── Reattribution ────────────────────────────────────────────────────────────

def reattribute_by_schedule(resultado: dict, schedule: dict) -> dict:
    """
    Reattribute recintos entre departamentos del schedule si mejora max|Δ| ≥10%.
    Modifica el resultado in-place y devuelve un log de cambios.

    Estrategia: para cada par de deptos del schedule con mismo area_total_m2,
    si uno esta sobrecargado y el otro subcargado, intentar mover recintos.
    """
    if not schedule or not schedule.get("tiene_tabla"):
        return {"aplicado": False, "razon": "sin schedule"}

    deptos_sched = schedule.get("departamentos", [])
    if len(deptos_sched) < 2:
        return {"aplicado": False, "razon": "menos de 2 deptos en schedule"}

    recintos = resultado.get("recintos", [])

    # Agrupar recintos por departamento
    by_depto: dict[str, list[dict]] = {}
    for r in recintos:
        d = r.get("departamento") or ""
        by_depto.setdefault(d, []).append(r)

    def _sum_area(recs: list[dict]) -> float:
        return sum(r.get("area_m2") or 0 for r in recs)

    def _max_delta_pct(by_d: dict[str, list[dict]]) -> float:
        peor = 0.0
        for sd in deptos_sched:
            sched_total = sd.get("area_total_m2") or 0
            if sched_total <= 0:
                continue
            sid = _norm(sd.get("id", ""))
            ext = 0.0
            for k, recs in by_d.items():
                kn = _norm(k)
                if sid == kn or sid in kn or kn in sid:
                    ext += _sum_area(recs)
            pct = abs(ext - sched_total) / sched_total * 100
            peor = max(peor, pct)
        return peor

    error_inicial = _max_delta_pct(by_depto)

    # Buscar pares con mismo area_total y delta opuesto significativo
    mejor_swap = None
    mejor_error = error_inicial

    for i, sa in enumerate(deptos_sched):
        sa_total = sa.get("area_total_m2") or 0
        sa_id_norm = _norm(sa.get("id", ""))
        if sa_total <= 0:
            continue
        for sb in deptos_sched[i+1:]:
            sb_total = sb.get("area_total_m2") or 0
            sb_id_norm = _norm(sb.get("id", ""))
            if sb_total <= 0:
                continue
            # Solo pares con mismo total (tipos iguales)
            if abs(sa_total - sb_total) / sa_total > 0.05:
                continue

            # Calcular extraido actual por cada lado
            ext_a = sum(_sum_area(recs) for k, recs in by_depto.items()
                        if sa_id_norm in _norm(k) or _norm(k) in sa_id_norm)
            ext_b = sum(_sum_area(recs) for k, recs in by_depto.items()
                        if sb_id_norm in _norm(k) or _norm(k) in sb_id_norm)

            # Si uno sobra y el otro falta
            if ext_a > sa_total * 1.3 and ext_b < sb_total * 0.7:
                # Mover de A a B: probar mover los recintos con area mas cercana al deficit
                deficit = sb_total - ext_b
                excess = ext_a - sa_total
                candidatos_keys = [k for k in by_depto if sa_id_norm in _norm(k) or _norm(k) in sa_id_norm]
                for ck in candidatos_keys:
                    for rec in list(by_depto[ck]):
                        a = rec.get("area_m2") or 0
                        if 0 < a <= max(deficit, excess) * 1.2:
                            # Probar el swap
                            backup = rec.get("departamento")
                            rec["departamento"] = sb.get("id")
                            err = _max_delta_pct(by_depto)
                            if err < mejor_error * 0.9:  # mejora >=10%
                                mejor_error = err
                                mejor_swap = {
                                    "from": ck, "to": sb.get("id"),
                                    "rec": rec.get("nombre"), "area": a,
                                    "error_antes": error_inicial,
                                    "error_despues": err,
                                }
                            else:
                                rec["departamento"] = backup  # revertir
            elif ext_b > sb_total * 1.3 and ext_a < sa_total * 0.7:
                # Caso simetrico B→A: se aplica recursivamente en otra iteracion
                pass

    if mejor_swap:
        # Marcar el recinto reasignado
        for r in recintos:
            if r.get("nombre") == mejor_swap["rec"] and r.get("departamento") == mejor_swap["to"]:
                r["nota_reattribution"] = "reatribuido por reconciliacion de schedule"
                r["confianza"] = (r.get("confianza") or 0.7) * 0.85
                break
        return {
            "aplicado": True,
            **mejor_swap,
        }

    return {"aplicado": False, "razon": f"sin mejora >=10% (error inicial {error_inicial:.1f}%)"}
