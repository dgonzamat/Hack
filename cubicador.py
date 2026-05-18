"""
Cubicador: convierte recintos extraidos + muros + vanos en cantidades por partida.

Entrada: el dict del JSON producido por poc_cubicacion.py (v4 o v5)
Salida: lista de partidas con cantidad, unidad y desglose por recinto.
"""

import copy
import math
import pickle
import re
import unicodedata
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
    r"\b(CALZADA|PISTA|VEREDA|TUNEL|PORTAL|CUNETA|PUENTE|ROTONDA|VIADUCTO|BERMA|CARRIL|"
    r"TERRAPLEN|CORTE|ESCARPE|DESMONTE|ALCANTARILLA|CANAL|ACEQUIA|DEMARCACION|"
    r"SENALETIVA|SENALIZACION|ILUMINACION|LUMINARIA|GUARDAVIA|DEFENSA CAMINERA|"
    r"REVEGETACION|PASARELA|ADOQUIN|EMPEDRADO|BARRERA|POZO|MEJORAMIENTO|SUBRASANTE|"
    r"COLECTOR|TUBERIA|ALCANTARILLADO|DREN|PASO SUPERIOR|PASO BAJO NIVEL|"
    r"ENSANCHE|SOBREANCHO|RELLENO|EXCAVACION|MEDIANA|TROCHA|ASFALTADO|"
    r"RAMPA|ANDEN|VADO|GEOTEXTIL|GEOMALLA|AFIRMADO)\b"
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
    """Normaliza nombre: mayusculas, sin acentos, sin guiones/barras, sin espacios extra. Mantiene puntos."""
    sin_acentos = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sin_acentos.upper().replace("-", " ").replace("/", " ")).strip()


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


# ─── Secciones transversales civiles ──────────────────────────────────────────

_DEFAULT_SECCIONES: dict = {
    "tunel": {
        "ancho_excav_m": 8.5,
        "alto_excav_m": 7.5,
        "espesor_revestimiento_m": 0.40,
        "kg_acero_por_m3_revest": 80,
    },
    "galeria": {
        "ancho_excav_m": 3.5,
        "alto_excav_m": 3.5,
        "espesor_revestimiento_m": 0.30,
        "kg_acero_por_m3_revest": 70,
    },
    "tunel_metro": {
        "diametro_excav_m": 6.0,
        "espesor_dovelas_m": 0.30,
        "kg_acero_por_m3_dovela": 100,
    },
    "puente": {
        "ancho_tablero_m": 10.0,
        "espesor_tablero_m": 0.55,
        "kg_acero_por_m3_tablero": 120,
        "estribo_factor": 0.0,      # vol_estribo = vol_tablero × factor (0.35 tipico MOP)
    },
    "muro_contencion": {
        "espesor_m": 0.40,
        "kg_acero_por_m3": 80,
        "zapata_factor": 0.0,       # vol_zapata = vol_muro × factor (0.30 para voladizo tipico MOP)
        "geotextil_factor": 0.0,    # area_geotextil = area × factor (1.1 para muro con drenaje)
    },
    "pavimento_flexible": {
        "carpeta_asfaltica_m": 0.06,
        "base_granular_m": 0.20,
        "sub_base_granular_m": 0.20,
        "subrasante_m": 0.15,    # e=150mm subrasante compactada/estabilizada (MOP estandar)
    },
    "pavimento_rigido": {
        "losa_hormigon_m": 0.22,
        "sub_base_m": 0.15,
    },
    "cuneta": {"ancho_m": 0.40},
    "vereda": {"espesor_hormigon_m": 0.10},
    "corte": {
        "profundidad_media_m": 3.00,  # profundidad media de corte en roca/tierra
    },
    "canal": {
        "ancho_m": 2.00,              # ancho interno canal revestido
    },
    "pasarela": {
        "espesor_tablero_m": 0.25,    # tablero liviano pasarela peatonal
        "kg_acero_por_m3_tablero": 80,
    },
    "terraplen": {
        "altura_media_m": 2.00,
    },
    "alcantarilla": {
        "ancho_interno_m": 1.50,
    },
    "senaletiva": {
        "area_m2_por_senal": 1.50,
    },
    "iluminacion": {
        "m2_por_poste": 4.00,
    },
    "defensa_vial": {
        "ancho_m": 0.50,
    },
    "barrera_nj": {
        "ancho_m": 0.60,          # ancho base barrera New Jersey
    },
    "pozo_inspeccion": {
        "m2_por_pozo": 4.00,      # huella en planta por pozo (2m × 2m tipico)
    },
    "mejoramiento_suelo": {},     # sin parametros: m² directa
    "calzada_granular": {         # camino ripio/afirmado sin carpeta asfaltica
        "base_granular_m": 0.20,
        "sub_base_granular_m": 0.20,
    },
    "colector": {
        "ancho_zanja_m": 0.80,    # ancho zanja excavacion (ml = area / ancho_zanja)
    },
}

# Elementos que contienen palabras de categorías viales pero NO son obras de infraestructura
_VIAL_SKIP = re.compile(r"\b(MIRADOR|PARADERO|PLAZOLETA|BALCON)\b")

# Categoría simple de elemento vial → lógica de cubicación
_VIAL_CATS = [
    # ── Senaletiva y equipamiento vial (antes que CALZADA — pueden incluir la palabra como calificador)
    (re.compile(r"\b(DEMARCACION|LINEAS DE TRAFICO|TACHAS|TACHONES)\b"), "demarcacion"),
    (re.compile(r"\b(SENALETIVA|SENALIZACION|SENAL VIAL)\b"), "senaletiva"),
    (re.compile(r"\b(ILUMINACION|LUMINARIA|ALUMBRADO VIAL|POSTE LUZ)\b"), "iluminacion"),
    (re.compile(r"\b(BARRERA HORMIGON|NEW JERSEY|BARRERA NJ|BARRERA RIGIDA|MURO NEW JERSEY)\b"), "barrera_nj"),
    (re.compile(r"\b(DEFENSA CAMINERA|GUARDAVIA|BARRERA METALICA|GUARDARAIL|PRETIL)\b"), "defensa_vial"),
    (re.compile(r"\b(POZO DE INSPECCION|CAMARA DE INSPECCION|POZO VISITA|SUMIDERO|POZO AGUAS)\b"), "pozo_inspeccion"),
    (re.compile(r"\b(MEJORAMIENTO SUBRASANTE|MEJORAMIENTO SUELO|ESTABILIZACION CAL|SUELO CAL|SUELO CEMENTO|SUBBASE TRATADA|SUBRASANTE TRATADA)\b"), "mejoramiento_suelo"),
    (re.compile(r"\b(GEOTEXTIL|GEOMALLA|GEOCOMPUESTO|GEOCOMPOSITE|GEOSINTETICO)\b"), "geotextil"),
    (re.compile(r"\b(REVEGETACION|HIDROSIEMBRA|COBERTURA VEGETAL|SIEMBRA TALUD|MEDIANA VERDE|MEDIANA CENTRAL|SEPARADOR VEGETAL|SEPARADOR CENTRAL)\b"), "revegetacion"),
    # ── Movimiento de tierras y drenaje (antes que CALZADA)
    (re.compile(r"\b(TERRAPLEN|RELLENO COMPACTADO|RELLENO ESTRUCTURAL|RELLENO ZANJA|EMBANQUE|CORTE Y RELLENO)\b"), "terraplen"),
    (re.compile(r"\b(CORTE EN ROCA|CORTE EN TIERRA|EXCAVACION EN CORTE|EXCAVACION MASIVA|EXCAVACION GENERAL|DESMONTE|BANCO DE PRESTAMO|TRINCHERA)\b"), "corte"),
    (re.compile(r"\b(ESCARPE|LIMPIEZA DE TERRENO|ROCE LIMPIEZA|DESCAPOTE|DESBOSQUE)\b"), "escarpe"),
    (re.compile(r"\b(ALCANTARILLA|DRENAJE TRANSVERSAL|CAJON HORMIGON|BÓVEDA PREFAB|BOVEDA PREFAB)\b"), "alcantarilla"),
    (re.compile(r"\b(CANAL|ACEQUIA|ZANJA COLECTORA)\b"), "canal"),
    (re.compile(r"\b(COLECTOR|TUBERIA DRENAJE|TUBERIA PVC|DREN FRANCES|DREN LONGITUDINAL|RED DRENAJE|ALCANTARILLADO)\b"), "colector"),
    # ── Estructuras de pavimento
    (re.compile(r"\b(AFIRMADO GRANULAR|PAVIMENTO GRANULAR|CAMINO RIPIO|RIPIO COMPACTADO|GRAVA COMPACTADA|CAMINO GRANULAR|CAMINO DE SERVICIO|CAMINO VECINAL)\b"), "calzada_granular"),
    (re.compile(r"\b(CALZADA|BERMA|ENSANCHE|SOBREANCHO|DESVIO PROVISIONAL|PLATAFORMA VIAL|CAMINO DE ACCESO|VIA DE SERVICIO|VIA RAPIDA|VIA EXPRESA|VIA TRONCAL|VIA COLECTORA|VIA LOCAL|AUTOPISTA|ROTONDA|GLORIETA|ASFALTADO|TROCHA|PATIO DE MANIOBRAS|RAMPA VEHICULAR|RAMPA ACCESO|ACCESO VEHICULAR|PAVIMENTO ASFALTICO|PAVIMENTO BITUMINOSO|CONCRETO ASFALTICO|RECARPETEO|BACHEO|CARPETA ASFALTICA|MEZCLA ASFALTICA)\b"), "calzada"),
    (re.compile(r"\bPISTA\b"), "calzada"),
    (re.compile(r"\b(PAVIMENTO HORMIGON|PAVIMENTO RIGIDO|LOSA DE HORMIGON CALZADA)\b"), "calzada_rigida"),
    (re.compile(r"\b(ADOQUIN|PAVIMENTO ARTICULADO|EMPEDRADO|MEDIANA PAVIMENTADA|MEDIANA ADOQUIN)\b"), "adoquin"),
    (re.compile(r"\b(VEREDA|ACERA|BANQUETA|ANDEN|PLATAFORMA PEATONAL|VADO PEATONAL)\b"), "vereda"),
    (re.compile(r"\b(CICLOVIA|CICLOBANDA|CICLOACERA|SENDA PEATONAL|PISTA BICI)\b"), "ciclovia"),
    (re.compile(r"\b(CUNETA|ZANJON|FOSO|SOLERA|BADEN)\b"), "cuneta"),
    (re.compile(r"\b(MURO DE CONTENCION|MURO PANTALLA|MURO BERLINES|MURO DE GAVIONES|TALUD|ESCOLLERA)\b"), "muro"),
    # ── Túneles (orden importa: tunel_metro y galeria antes de tunel)
    (re.compile(r"\b(TUNEL METRO|TUBO METRO|TUNEL TBM|TUNEL FERROVIARIO|TUNEL CIRCULAR)\b"), "tunel_metro"),
    (re.compile(r"\b(GALERIA|BOVEDA|HASTIAL)\b"), "galeria"),
    (re.compile(r"\b(TUNEL|PORTAL)\b"), "tunel"),
    (re.compile(r"\b(REVESTIMIENTO TUNEL|SHOTCRETE|HORMIGON PROYECTADO|CONTRABOVEDA)\b"), "revestimiento_tunel"),
    # ── Estructuras tipo puente
    (re.compile(r"\b(PASARELA|PASO SUPERIOR PEATONAL|PASO A DESNIVEL PEAT)\b"), "pasarela"),
    (re.compile(r"\b(PUENTE|VIADUCTO|TABLERO|ESTRIBO|LOSA DE PUENTE|LOSA DE APROXIMACION|PASO SUPERIOR VEHICULAR|PASO BAJO NIVEL|PASO DESNIVEL VIAL)\b"), "puente"),
]


def _cat_vial(n_norm: str) -> Optional[str]:
    if _VIAL_SKIP.search(n_norm):
        return None
    for regex, cat in _VIAL_CATS:
        if regex.search(n_norm):
            return cat
    return None


def _merge_sec(secciones: Optional[dict]) -> dict:
    """Combina secciones del usuario con defaults (deep merge por clave raiz)."""
    result = copy.deepcopy(_DEFAULT_SECCIONES)
    if secciones:
        for k, v in secciones.items():
            if k in result and isinstance(v, dict):
                result[k].update(v)
            else:
                result[k] = v
    return result


def _acum(
    acc: dict, partida: str, unidad: str, cantidad: float,
    descripcion: str, nombre: str, supuesto: str = "",
) -> None:
    """Acumula cantidad en la partida dada, creando la entrada si no existe."""
    if partida not in acc:
        acc[partida] = {
            "partida": partida,
            "descripcion": descripcion,
            "unidad": unidad,
            "cantidad": 0.0,
            "tipo": "vial",
            "supuesto": supuesto,
            "elementos": [],
        }
    acc[partida]["cantidad"] += cantidad
    acc[partida]["elementos"].append({"nombre": nombre})


def cubicar_vial(viales_detectados: list[dict], secciones: Optional[dict] = None) -> list[dict]:
    """
    Genera partidas civiles desde elementos viales detectados.

    secciones: dict cargado desde secciones_civiles.yaml (opcional).
    Si no se provee, usa dimensiones tipicas MOP/Metro (ver _DEFAULT_SECCIONES).

    Categorias y formulas (29 activas):
    - calzada flexible    → carpeta + base + sub-base + subrasante (m²) + excav (m³)
    - calzada_rigida      → pavimento hormigon + sub-base (m²)
    - calzada_granular    → base + sub-base (m²) + excav (m³); sin carpeta asfaltica
    - vereda / anden      → acera hormigon + base (m²)
    - ciclovia            → ciclovia_pavimento m²
    - cuneta              → ml = area / ancho_cuneta
    - tunel (rect.)       → excavacion m³; revestimiento m²; acero kg
    - galeria             → igual que tunel con seccion galeria
    - tunel_metro (TBM)   → seccion circular; dovelas m²; acero kg
    - revestimiento_tunel → shotcrete / hormigon proyectado m²
    - puente              → hormigon m³; acero kg; moldaje m² (+ estribos opcional)
    - pasarela            → hormigon m³; acero kg; moldaje m² (seccion liviana)
    - muro                → muro_contencion_hormigon m² all-inclusive (+ geotextil opcional)
    - corte               → m³ = area × profundidad_media
    - escarpe             → escarpe_y_limpieza m²
    - terraplen           → m³ = area × altura_media
    - alcantarilla        → ml = area / ancho_interno
    - canal               → ml = area / ancho_canal
    - colector            → ml = area / ancho_zanja; PVC o hormigon por keyword
    - adoquin             → pavimento_adoquin m²
    - demarcacion         → demarcacion_vial m²
    - senaletiva          → un = area / m²_por_senal
    - iluminacion         → un = area / m²_por_poste
    - defensa_vial        → ml = area / ancho_guardavia
    - barrera_nj          → ml = area / ancho_barrera
    - pozo_inspeccion     → un = area / m²_por_pozo
    - mejoramiento_suelo  → mejoramiento_suelo_cal m²
    - geotextil           → geotextil_drenaje m²
    - revegetacion        → revegetacion_hidrosiembra m²
    """
    sec = _merge_sec(secciones)
    acc: dict[str, dict] = {}

    for elem in viales_detectados:
        nombre = elem.get("nombre", "?")
        area = elem.get("area_m2") or 0.0
        if area <= 0:
            continue

        cat = _cat_vial(_norm(nombre))
        if cat is None:
            continue

        if cat == "calzada":
            pav = sec["pavimento_flexible"]
            cap = pav["carpeta_asfaltica_m"]
            base = pav["base_granular_m"]
            sub = pav["sub_base_granular_m"]
            sub_ras = pav.get("subrasante_m", 0.0)
            _acum(acc, "carpeta_asfaltica_e60mm", "m2", area,
                  f"Carpeta asfaltica e={int(cap*1000)}mm", nombre,
                  f"area directa; e={cap*1000:.0f} mm")
            _acum(acc, "base_granular_e200mm", "m2", area,
                  f"Base granular e={int(base*1000)}mm", nombre,
                  f"area directa; e={base*1000:.0f} mm")
            _acum(acc, "sub_base_granular_e200mm", "m2", area,
                  f"Sub-base granular e={int(sub*1000)}mm", nombre,
                  f"area directa; e={sub*1000:.0f} mm")
            if sub_ras > 0:
                _acum(acc, "subrasante_estabilizada", "m2", area,
                      f"Subrasante estabilizada e={int(sub_ras*1000)}mm", nombre,
                      f"area directa; e={sub_ras*1000:.0f} mm")
            total_excav = cap + base + sub + sub_ras
            _acum(acc, "excavacion_tierra_comun", "m3", area * total_excav,
                  "Excavacion tierra comun", nombre,
                  f"area × {total_excav:.2f} m (paquete estructural)")

        elif cat == "calzada_granular":
            gr = sec["calzada_granular"]
            base_g = gr["base_granular_m"]
            sub_g = gr["sub_base_granular_m"]
            _acum(acc, "base_granular_e200mm", "m2", area,
                  f"Base granular e={int(base_g*1000)}mm camino granular", nombre,
                  f"area directa; e={base_g*1000:.0f} mm")
            _acum(acc, "sub_base_granular_e200mm", "m2", area,
                  f"Sub-base granular e={int(sub_g*1000)}mm camino granular", nombre,
                  f"area directa; e={sub_g*1000:.0f} mm")
            total_excav_g = base_g + sub_g
            _acum(acc, "excavacion_tierra_comun", "m3", area * total_excav_g,
                  "Excavacion tierra comun camino granular", nombre,
                  f"area × {total_excav_g:.2f} m (base + sub-base)")

        elif cat == "calzada_rigida":
            pr = sec["pavimento_rigido"]
            losa_m = pr["losa_hormigon_m"]
            sub_m = pr["sub_base_m"]
            _acum(acc, "pavimento_hormigon_rigido", "m2", area,
                  f"Pavimento hormigon rigido e={int(losa_m*100)}cm", nombre,
                  f"area directa; e={losa_m*1000:.0f} mm")
            _acum(acc, "sub_base_granular_e200mm", "m2", area,
                  f"Sub-base granular e={int(sub_m*1000)}mm", nombre,
                  f"area directa; e={sub_m*1000:.0f} mm")

        elif cat == "vereda":
            esp_v = sec["vereda"]["espesor_hormigon_m"]
            _acum(acc, "acera_hormigon_e10cm", "m2", area,
                  f"Acera hormigon e={int(esp_v*100)}cm", nombre,
                  f"area directa; e={esp_v*100:.0f} cm")
            _acum(acc, "base_granular_e200mm", "m2", area,
                  "Base granular vereda", nombre, "area directa")

        elif cat == "ciclovia":
            _acum(acc, "ciclovia_pavimento", "m2", area,
                  "Ciclovia pavimento", nombre, "area directa")

        elif cat == "cuneta":
            ancho = sec["cuneta"]["ancho_m"]
            _acum(acc, "cuneta_hormigon_revestida", "ml", area / ancho,
                  f"Cuneta hormigon revestida a={ancho:.2f}m", nombre,
                  f"area / {ancho:.2f} m ancho cuneta")

        elif cat in ("tunel", "galeria"):
            # Galeria usa su propia seccion si existe; fallback a tunel
            s = sec["galeria"] if cat == "galeria" else sec["tunel"]
            ancho = s["ancho_excav_m"]
            alto = s["alto_excav_m"]
            esp_rev = s["espesor_revestimiento_m"]
            kg_ac = s["kg_acero_por_m3_revest"]
            longitud = area / ancho
            v_excav = longitud * ancho * alto    # = area_planta × alto
            perim_sec = 2 * (ancho + alto)
            area_rev = longitud * perim_sec
            v_rev = area_rev * esp_rev
            tipo_label = "galeria" if cat == "galeria" else "tunel"
            _acum(acc, "excavacion_tunel_roca", "m3", v_excav,
                  f"Excavacion {tipo_label} {ancho:.1f}×{alto:.1f} m", nombre,
                  f"seccion {ancho:.1f}×{alto:.1f} m — ajustar en secciones_civiles.yaml")
            _acum(acc, "revestimiento_tunel_hormigon", "m2", area_rev,
                  f"Revestimiento {tipo_label} hormigon e={int(esp_rev*100)}cm", nombre,
                  f"perim sec {perim_sec:.1f} m × longitud {longitud:.0f} m")
            _acum(acc, "acero_refuerzo_a630", "kg", v_rev * kg_ac,
                  "Acero refuerzo A630-42H", nombre,
                  f"{kg_ac} kg/m³ revestimiento {tipo_label}")

        elif cat == "tunel_metro":
            s = sec["tunel_metro"]
            diam = s["diametro_excav_m"]
            esp_dov = s["espesor_dovelas_m"]
            kg_ac = s["kg_acero_por_m3_dovela"]
            # Seccion circular TBM: area_sec = π×(d/2)²; longitud = area_planta / d
            area_sec = math.pi * (diam / 2) ** 2
            longitud = area / diam
            v_excav = longitud * area_sec
            perim_sec = math.pi * diam
            area_rev = longitud * perim_sec
            v_dov = area_rev * esp_dov
            _acum(acc, "excavacion_tunel_roca", "m3", v_excav,
                  f"Excavacion tunel metro D={diam:.1f} m", nombre,
                  f"seccion circular D={diam:.1f} m — ajustar en secciones_civiles.yaml")
            _acum(acc, "revestimiento_tunel_hormigon", "m2", area_rev,
                  f"Dovelas hormigon e={int(esp_dov*100)}cm", nombre,
                  f"perim sec {perim_sec:.2f} m × longitud {longitud:.0f} m")
            _acum(acc, "acero_refuerzo_a630", "kg", v_dov * kg_ac,
                  "Acero refuerzo A630-42H dovelas", nombre,
                  f"{kg_ac} kg/m³ dovelas")

        elif cat == "revestimiento_tunel":
            _acum(acc, "revestimiento_tunel_hormigon", "m2", area,
                  "Revestimiento tunel hormigon", nombre, "area directa")

        elif cat == "puente":
            s = sec["puente"]
            esp = s["espesor_tablero_m"]
            kg_ac = s["kg_acero_por_m3_tablero"]
            estr_factor = s.get("estribo_factor", 0.0)
            v_tab = area * esp
            _acum(acc, "hormigon_armado_H30", "m3", v_tab,
                  f"Hormigon armado H30 tablero e={int(esp*100)}cm", nombre,
                  f"area × {esp:.2f} m espesor tablero — ajustar en secciones_civiles.yaml")
            _acum(acc, "acero_refuerzo_a630", "kg", v_tab * kg_ac,
                  "Acero refuerzo A630-42H", nombre,
                  f"{kg_ac} kg/m³ tablero")
            _acum(acc, "moldaje_tablero", "m2", area * 2,
                  "Moldaje tablero puente", nombre,
                  "area × 2 caras (intrados + prelosa)")
            if estr_factor > 0:
                v_estr = v_tab * estr_factor
                _acum(acc, "hormigon_armado_H30", "m3", v_estr,
                      "Hormigon armado H30 estribos", nombre,
                      f"vol_tablero × {estr_factor:.2f} estribo_factor — ajustar en secciones_civiles.yaml")
                _acum(acc, "acero_refuerzo_a630", "kg", v_estr * kg_ac,
                      "Acero refuerzo A630-42H estribos", nombre,
                      f"{kg_ac} kg/m³ estribos")

        elif cat == "muro":
            s = sec["muro_contencion"]
            # All-inclusive m2: precio ONDAC incluye hormigon + acero + moldaje + colocacion
            # Evita doble conteo vs sumar componentes por separado
            _acum(acc, "muro_contencion_hormigon", "m2", area,
                  "Muro de contencion hormigon (all-inclusive)", nombre,
                  "precio ONDAC $95.000/m2 incluye hormigon + acero + moldaje")
            geo_factor = s.get("geotextil_factor", 0.0)
            if geo_factor > 0:
                _acum(acc, "geotextil_drenaje", "m2", area * geo_factor,
                      "Geotextil drenaje trasdos muro", nombre,
                      f"area × {geo_factor:.2f} (solape incluido)")

        elif cat == "corte":
            prof = sec["corte"]["profundidad_media_m"]
            _acum(acc, "excavacion_en_corte", "m3", area * prof,
                  f"Excavacion en corte h_media={prof:.1f}m", nombre,
                  f"area × {prof:.1f} m — ajustar en secciones_civiles.yaml")

        elif cat == "escarpe":
            _acum(acc, "escarpe_y_limpieza", "m2", area,
                  "Escarpe y limpieza terreno vegetal", nombre, "area directa")

        elif cat == "canal":
            ancho = sec["canal"]["ancho_m"]
            _acum(acc, "canal_hormigon_revestido", "ml", area / ancho,
                  f"Canal hormigon revestido a={ancho:.1f}m", nombre,
                  f"area / {ancho:.2f} m ancho canal")

        elif cat == "colector":
            ancho_z = sec["colector"]["ancho_zanja_m"]
            n_norm = _norm(nombre)
            es_hormigon = bool(re.search(r"\b(HORMIGON|HA\b|CONCRETO|CAC|CAÑO)\b", n_norm))
            partida_col = "colector_hormigon_600mm" if es_hormigon else "colector_pvc_300mm"
            _acum(acc, partida_col, "ml", area / ancho_z,
                  f"{'Colector hormigon 600mm' if es_hormigon else 'Colector PVC 300mm'} ({ancho_z:.2f}m zanja)",
                  nombre, f"area / {ancho_z:.2f} m ancho zanja — ajustar en secciones_civiles.yaml")

        elif cat == "pasarela":
            s = sec["pasarela"]
            esp = s["espesor_tablero_m"]
            kg_ac = s["kg_acero_por_m3_tablero"]
            v_tab = area * esp
            _acum(acc, "hormigon_armado_H30", "m3", v_tab,
                  f"Hormigon armado H30 pasarela e={int(esp*100)}cm", nombre,
                  f"area × {esp:.2f} m — ajustar en secciones_civiles.yaml")
            _acum(acc, "acero_refuerzo_a630", "kg", v_tab * kg_ac,
                  "Acero refuerzo A630-42H pasarela", nombre,
                  f"{kg_ac} kg/m³ tablero pasarela")
            _acum(acc, "moldaje_tablero", "m2", area * 2,
                  "Moldaje tablero pasarela", nombre,
                  "area × 2 caras")

        elif cat == "adoquin":
            _acum(acc, "pavimento_adoquin_hormigon", "m2", area,
                  "Pavimento adoquin hormigon sobre lecho arena", nombre, "area directa")

        elif cat == "barrera_nj":
            ancho = sec["barrera_nj"]["ancho_m"]
            _acum(acc, "barrera_hormigon_nj", "ml", area / ancho,
                  f"Barrera hormigon tipo New Jersey a={ancho:.2f}m", nombre,
                  f"area / {ancho:.2f} m ancho base")

        elif cat == "pozo_inspeccion":
            m2_pozo = sec["pozo_inspeccion"]["m2_por_pozo"]
            n_pozos = max(1, round(area / m2_pozo))
            _acum(acc, "pozo_inspeccion_hormigon", "un", n_pozos,
                  "Pozo de inspeccion hormigon armado", nombre,
                  f"area / {m2_pozo:.1f} m² por pozo")

        elif cat == "mejoramiento_suelo":
            _acum(acc, "mejoramiento_suelo_cal", "m2", area,
                  "Mejoramiento subrasante con cal/cemento", nombre, "area directa")

        elif cat == "terraplen":
            altura = sec["terraplen"]["altura_media_m"]
            _acum(acc, "terraplen_compactado", "m3", area * altura,
                  f"Terraplen compactado h_media={altura:.1f}m", nombre,
                  f"area × {altura:.1f} m — ajustar en secciones_civiles.yaml")

        elif cat == "alcantarilla":
            ancho = sec["alcantarilla"]["ancho_interno_m"]
            _acum(acc, "alcantarilla_marco_hormigon", "ml", area / ancho,
                  f"Alcantarilla marco hormigon a={ancho:.1f}m", nombre,
                  f"area / {ancho:.2f} m ancho interno")

        elif cat == "demarcacion":
            _acum(acc, "demarcacion_vial_termoplastico", "m2", area,
                  "Demarcacion vial termoplastico", nombre, "area directa")

        elif cat == "senaletiva":
            a_senal = sec["senaletiva"]["area_m2_por_senal"]
            n_senales = max(1, round(area / a_senal))
            _acum(acc, "senal_vial_retrorreflectante", "un", n_senales,
                  f"Senal vial retroreflectante ({a_senal:.1f}m²/señal)", nombre,
                  f"area / {a_senal:.1f} m² por señal — ajustar en secciones_civiles.yaml")

        elif cat == "iluminacion":
            m2_poste = sec["iluminacion"]["m2_por_poste"]
            n_postes = max(1, round(area / m2_poste))
            _acum(acc, "luminaria_led_vial", "un", n_postes,
                  "Luminaria LED vial (poste + luminaria + instalacion)", nombre,
                  f"area / {m2_poste:.1f} m² por poste — ajustar en secciones_civiles.yaml")

        elif cat == "defensa_vial":
            ancho = sec["defensa_vial"]["ancho_m"]
            _acum(acc, "guardavia_flexible_w", "ml", area / ancho,
                  "Guardavia flexible W-beam doble ola", nombre,
                  f"area / {ancho:.2f} m ancho planta")

        elif cat == "geotextil":
            _acum(acc, "geotextil_drenaje", "m2", area,
                  "Geotextil / geomalla separacion-drenaje", nombre, "area directa")

        elif cat == "revegetacion":
            _acum(acc, "revegetacion_hidrosiembra", "m2", area,
                  "Revegetacion hidrosiembra taludes", nombre, "area directa")

    result = []
    for p in acc.values():
        p["cantidad"] = round(p["cantidad"], 1)
        result.append(p)
    return result


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
    secciones: Optional[dict] = None,
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

    # Puertas: separar por tipo simple/doble segun keyword en tipo
    _RE_PUERTA_DOBLE = re.compile(r"\b(DOBLE|150|D150|D-150|PPAL|PRINCIPAL 150)\b")
    puertas_simples = 0
    puertas_dobles = 0
    for v in vanos.get("puertas", []):
        cant = v.get("cantidad", 1) or 1
        tipo_p = _norm(v.get("tipo", ""))
        if _RE_PUERTA_DOBLE.search(tipo_p):
            puertas_dobles += cant
        else:
            puertas_simples += cant
    if puertas_simples > 0:
        partidas.append({
            "partida": "puerta_simple_90cm_instalada",
            "descripcion": "Puerta simple 90cm instalada",
            "unidad": "un",
            "cantidad": puertas_simples,
            "nota": "conteo puertas tipo simple",
        })
    if puertas_dobles > 0:
        partidas.append({
            "partida": "puerta_doble_150cm_instalada",
            "descripcion": "Puerta doble 150cm instalada",
            "unidad": "un",
            "cantidad": puertas_dobles,
            "nota": "conteo puertas tipo doble/principal",
        })

    if ventanas_area > 0:
        partidas.append({
            "partida": "ventana_corredera_aluminio",
            "descripcion": "Ventana corredera aluminio",
            "unidad": "m2",
            "cantidad": round(ventanas_area, 1),
            "nota": "area unitaria × cantidad por tipo",
        })

    # Partidas civiles desde elementos viales detectados
    partidas_vial = cubicar_vial(viales_detectados, secciones=secciones)
    partidas.extend(partidas_vial)

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
