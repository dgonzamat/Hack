#!/usr/bin/env python3
"""
Entrena clasificador ML de recintos: húmedo / seco / exterior / común / vial.

Dataset sintético ~1100 nombres típicos de construcción chilena.
Modelo: TF-IDF char+word FeatureUnion + LogisticRegression (C=5).
Salida: clasificador_recintos.pkl

Uso:
    python train_clasificador.py           # entrena + guarda pkl
    python train_clasificador.py --eval    # métricas CV sin guardar
    python train_clasificador.py --tune    # GridSearchCV (lento)
"""

import argparse
import pickle
import re
import unicodedata
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_predict, cross_val_score
from sklearn.pipeline import FeatureUnion, Pipeline

PKL_PATH = Path(__file__).parent / "clasificador_recintos.pkl"


def _norm(s: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sin_acentos.upper().replace("-", " ").replace("/", " ")).strip()


def _generar_dataset() -> list[tuple[str, str]]:
    datos: list[tuple[str, str]] = []

    def add(nombres: list[str], cat: str) -> None:
        for n in nombres:
            datos.append((_norm(n), cat))

    # ── HÚMEDO ───────────────────────────────────────────────────────────────
    add(["BAÑO", "WC", "TOILET", "DUCHA"], "humedo")
    for base in ["BAÑO", "WC", "BANO", "TOILET", "DUCHA"]:
        for n in ["1", "2", "3", "4"]:
            add([f"{base} {n}", f"{base}{n}"], "humedo")
    for q in ["PRINCIPAL", "SUITE", "COMPLETO", "SOCIAL", "SERVICIO", "VISITAS",
              "COMPARTIDO", "DUCHA", "TINA", "MEDIO", "MASTER", "EN SUITE"]:
        add([f"BAÑO {q}", f"BANO {q}", f"WC {q}"], "humedo")

    add(["COCINA", "KITCHENETTE", "COCINETA", "KITCHEN", "COCINA AMERICANA",
         "COCINA ABIERTA", "COCINA SEMI-ABIERTA", "COCINA INTEGRAL",
         "ANTECOCINA", "PANTRY", "WET BAR", "BAR MOJADO", "ISLA COCINA",
         "COCINA COMEDOR", "COCINA LIVING COMEDOR",
         "KITCHEN ABIERTA", "KITCHEN INTEGRADA", "KITCHEN COMEDOR",
         "KITCHENETTE ESTUDIO", "COCINETA ESTUDIO"], "humedo")

    add(["LOGIA", "LOGIA DE SERVICIO", "LOGIA SERVICIO",
         "LAVANDERIA", "LAVANDERÍA", "LAVAND.", "LAVAD.",
         "LAVADERO", "LAVADO", "PIEZA LAVADO",
         "ZONA DE LAVADO", "ZONA LAVADO", "AREA DE LAVADO",
         "CUARTO LAVADO", "PIEZA DE LAVADO", "PATIO LAVADO",
         "CUARTO DE SERVICIO HUMEDO"], "humedo")

    # Salas mecánicas con instalaciones hidráulicas (calderas, bombas, ACS)
    # NB: "SALA MAQUINAS EDIFICIO" se mantiene como común (ascensores) en bloque común
    add(["SALA DE MAQUINAS HIDRAULICA", "CUARTO DE MAQUINAS HIDRAULICAS",
         "SALA CALDERAS", "SALA CALDERA", "CUARTO CALDERAS", "CUARTO CALDERA",
         "SALA DE CALEFACCION", "CUARTO CALEFACCION",
         "SALA COMPRESORES PISCINA", "CUARTO COMPRESORES PISCINA",
         "SALA ACS", "CUARTO ACS", "SALA CLIMATIZACION HIDRONICA",
         "CUARTO TERMOTANQUES", "SALA ESTANQUES AGUA"], "humedo")

    add(["SH", "SSHH", "S.H.", "S.S.H.H.", "SS.HH.", "SS HH",
         "SERV HIG", "SERVICIO HIGIENICO", "SERVICIO HIGIÉNICO",
         "SERV. HIG.",
         "DUCHA COMUN", "DUCHA VESTUARIO", "DUCHA EXTERIOR",
         "TOILET SUITE", "TOILET MASTER", "TOILET SOCIAL",
         "SH 1", "SH 2", "SH VISITAS", "SSHH VISITAS"], "humedo")

    add(["COCINA-LAV", "COCINA LAV", "COCINA-LAVANDERIA",
         "COCINA LAVANDERIA", "COCINA LAVANDERÍA",
         "BAÑO-VESTIDOR", "BANO VESTIDOR",
         "CUARTO ASEO", "CUARTO BASURA", "DEPOSITO BASURA"], "humedo")

    # ── SECO ─────────────────────────────────────────────────────────────────
    add(["DORMITORIO", "DORM", "PIEZA", "HABITACION", "HABITACIÓN",
         "CUARTO", "RECAMARA", "RECÁMARA"], "seco")
    for base in ["DORMITORIO", "DORM", "PIEZA"]:
        for n in ["1", "2", "3", "4", "5"]:
            add([f"{base} {n}", f"{base}.{n}", f"{base}{n}"], "seco")
    for q in ["PRINCIPAL", "SUITE", "MASTER", "MATRIMONIAL", "SIMPLE",
              "DOBLE", "TRIPLE", "SERVICIO", "NIÑO", "NIÑOS", "BEBE",
              "VISITA", "ESTUDIO", "JUNIOR", "SECUNDARIO", "EXTRA"]:
        add([f"DORMITORIO {q}", f"DORM {q}", f"DORM. {q}"], "seco")
    add(["DORM.PRINCIPAL", "DORM.1", "DORM.2", "DORM.3", "DORM.SERV",
         "DORM.SUITE", "DORM.MATRIMONIAL"], "seco")

    add(["LIVING", "LIVING COMEDOR", "LIVING-COMEDOR", "LIVING DINING",
         "SALA DE ESTAR", "ESTAR", "FAMILY ROOM", "LOUNGE",
         "COMEDOR", "COMEDOR DIARIO", "SALA COMEDOR", "ANTECOMEDOR",
         "SALA DE TV", "SALA TV", "SALA MULTIMEDIA", "HOME THEATER",
         "SALA DE MUSICA", "SALA DE JUEGOS", "GAME ROOM",
         "SALA DE REUNIONES", "SALA REUNION", "SALA PRINCIPAL",
         "LIVING COMEDOR COCINA", "LIVING/COMEDOR/COCINA"], "seco")

    add(["WALK-IN CLOSET", "WALK IN CLOSET", "WALK IN", "WALK-IN",
         "CLOSET", "VESTIDOR", "VESTIDOR PRINCIPAL", "VESTIDOR SUITE",
         "DRESSING", "DRESSING ROOM", "GUARDAROPA", "GUARDARROPA",
         "WALK-IN 1", "WALK-IN 2", "CLOSET 1", "CLOSET 2",
         "VESTIDOR DORM", "VESTIDOR MASTER"], "seco")

    add(["OFICINA", "ESTUDIO", "ESCRITORIO", "BIBLIOTECA",
         "HOME OFFICE", "SALA DE ESTUDIO", "SALA DE TRABAJO",
         "DESPACHO", "GABINETE", "SALA ESTUDIO"], "seco")

    add(["DESPENSA", "BODEGA", "BODEGA PRIVADA", "BODEGA PROPIA",
         "BODEGA INDIVIDUAL", "BODEGA DEPARTAMENTO", "BODEGA INTERIOR",
         "BODEGA PISO", "DEPOSITO", "DEPÓSITO", "DEPOSITO PRIVADO",
         "BAULERA", "CUARTO DE SERVICIO", "PIEZA DE SERVICIO",
         "DORMITORIO SERVICIO", "DORM SERVICIO"], "seco")
    for n in ["1", "2", "3"]:
        add([f"BODEGA {n}", f"DEPOSITO {n}", f"BAULERA {n}"], "seco")

    add(["BOUDOIR", "SALA CUNA", "CUARTO CUNA", "NURSERY",
         "SALA DE LECTURA", "CUARTO DE COSTURA", "TALLER",
         "GIMNASIO", "GYM", "SALA DE EJERCICIO", "SALA DE YOGA",
         "SALA DE PLANCHA", "SALA INFANTIL", "SALA JUEGOS INFANTIL",
         "SALA MULTIMEDIA PRIVADA", "SALA DE LECTURA PRIVADA"], "seco")

    # ── EXTERIOR ─────────────────────────────────────────────────────────────
    add(["TERRAZA", "BALCON", "BALCÓN", "LOGGIA",
         "PATIO", "PATIO EXTERIOR", "PATIO INTERIOR", "PATIO DE SERVICIO",
         "JARDIN", "JARDÍN", "JARDIN FRONTAL", "JARDIN TRASERO",
         "ANTEJARDÍN", "ANTEJARDIN", "JARDIN ACCESO", "JARDIN INGRESO",
         "DECK", "TERRAZA DECK", "PATIO DECK",
         "QUINCHO", "PARRILLA", "ASADOR", "SOLARIUM",
         "PISCINA", "AREA PISCINA", "TERRAZA PISCINA",
         "ZONA VERDE", "AREA VERDE"], "exterior")
    for base in ["TERRAZA", "BALCON", "PATIO"]:
        for n in ["1", "2", "3"]:
            add([f"{base} {n}"], "exterior")
    for q in ["PRINCIPAL", "ACCESO", "POSTERIOR", "FRONTAL",
              "NORTE", "SUR", "ORIENTE", "PONIENTE",
              "LIVING", "DORMITORIO", "DORM", "MASTER"]:
        add([f"TERRAZA {q}", f"BALCON {q}", f"PATIO {q}"], "exterior")

    # ── COMÚN ─────────────────────────────────────────────────────────────────
    add(["HALL", "HALL DE ACCESO", "HALL DISTRIBUIDOR",
         "HALL DE DISTRIBUCIÓN", "HALL PRINCIPAL", "FOYER",
         "RECIBIDOR", "VESTIBULO", "VESTÍBULO",
         "ENTRADA", "ACCESO", "INGRESO",
         "ENTRADA EDIFICIO", "ACCESO EDIFICIO", "INGRESO EDIFICIO",
         "ACCESO PRINCIPAL", "INGRESO PRINCIPAL", "ENTRADA PRINCIPAL",
         "RECIBIDOR PRINCIPAL", "ACCESO PEATONAL"], "comun")

    add(["PASILLO", "PASILLO DE DISTRIBUCIÓN", "CORREDOR",
         "CORREDOR DE DISTRIBUCIÓN", "CIRCULACION", "CIRCULACIÓN",
         "AREA DE CIRCULACION", "ÁREA DE CIRCULACIÓN",
         "HALL CIRCULACION", "DISTRIBUCION", "DISTRIBUCIÓN"], "comun")

    add(["ESCALERA", "CAJA DE ESCALERA", "ESCALERA INTERIOR",
         "ESCALERA PRINCIPAL", "ESCALERA SERVICIO",
         "ASCENSOR", "CAJA ASCENSOR", "HALL ASCENSORES",
         "DUCTO", "DUCTO BASURA", "SHAFT", "SHAFT INSTALACIONES",
         "PATIO DE LUZ", "PATIO LUZ"], "comun")

    add(["RECEPCIÓN", "RECEPCION", "PORTERÍA", "PORTERIA",
         "SALA MULTIUSO", "SUM", "SALA DE USO MULTIPLE", "SALA USOS MULTIPLES",
         "BODEGA COMUN", "BODEGA COMÚN",
         "ESTACIONAMIENTO", "ESTACIONAMIENTO VISITAS",
         "CUARTO INSTALACIONES", "SALA TECNICA", "SALA MÁQUINAS",
         "CUARTO ELECTRICO", "SALA ELECTRICA",
         "SUM EDIFICIO", "SUM COMUN", "SUM RESIDENCIAL",
         "SALA TECNICA EDIFICIO", "SALA TECNICA PISO",
         "PORTERIA ACCESO", "PORTERIA PRINCIPAL"], "comun")

    # Lobby / accesos de edificio
    add(["LOBBY", "LOBBY PRINCIPAL", "LOBBY ACCESO", "LOBBY DE ACCESO",
         "VESTIBULO ASCENSORES", "HALL INTERMEDIO", "HALL PISO",
         "ANTESALA", "SALA DE ESPERA", "SALA VIP",
         "FOYER PRINCIPAL", "HALL LLEGADAS",
         "RECEPCION EDIFICIO", "RECEPCION PRINCIPAL"], "comun")

    # Circulación vertical y núcleos (calificadores de edificio explícitos)
    add(["CIRCULACION VERTICAL", "NUCLEO VERTICAL", "CAJA VERTICAL",
         "RAMPA VEHICULAR EDIFICIO", "RAMPA ACCESO EDIFICIO",
         "PASILLO TECNICO EDIFICIO", "CORREDOR TECNICO EDIFICIO",
         "CAJA ESCALERA SERVICIO", "ESCALERA INTERIOR SERVICIO",
         "SALA EVACUACION EDIFICIO", "ZONA EVACUACION EDIFICIO"], "comun")

    # Salas técnicas de edificio — siempre calificadas con EDIFICIO
    add(["SALA DE MAQUINAS EDIFICIO", "SALA MAQUINAS EDIFICIO",
         "CUARTO ELECTRICO EDIFICIO", "SALA ELECTRICA EDIFICIO",
         "SALA TABLEROS EDIFICIO", "CUARTO TABLEROS EDIFICIO",
         "SALA BOMBAS EDIFICIO", "CUARTO BOMBAS EDIFICIO",
         "SALA INCENDIO EDIFICIO", "CUARTO INCENDIO EDIFICIO", "SALA SPRINKLERS",
         "CUARTO DE MEDIDORES", "SALA DE MEDIDORES", "CUARTO MEDIDORES",
         "SALA GRUPO ELECTROGENO", "CUARTO GENERADOR EDIFICIO",
         "CUARTO DE BASURA", "SALA RESIDUOS", "SALA ACOPIO RESIDUOS",
         "SALA ASEO EDIFICIO", "CUARTO ASEO EDIFICIO", "DEPOSITO ASEO",
         "SALA CISTERNA", "CUARTO CISTERNA EDIFICIO"], "comun")

    # Áreas comunes residenciales
    add(["TERRAZA COMUN", "TERRAZA COMUNITARIA", "TERRAZA EDIFICIO",
         "ROOF GARDEN", "ROOFTOP", "ROOFTOP EDIFICIO", "TERRADO COMUN",
         "PATIO COMUN", "PATIO COMUNITARIO", "PATIO EDIFICIO", "JARDIN COMUN",
         "AREA PARRILLA COMUN", "QUINCHO COMUN", "ASADOR COMUN",
         "AREA SOCIAL COMUN", "SALON SOCIAL", "SALA EVENTOS EDIFICIO",
         "SALA COWORKING", "SALA ESTUDIO COMUN", "SALA TRABAJO COMUN",
         "SALA JUEGOS COMUN", "SALA INFANTIL COMUN", "AREA INFANTIL",
         "SALA FITNESS", "GYM COMUN", "AREA EJERCICIO COMUN",
         "SALA SPA", "SAUNA COMUN", "SALA YOGA COMUN",
         "LAVANDERIA COMUN", "AREA LAVADO COMUN", "CUARTO LAVADO COMUN",
         "BODEGA COMUN PISO", "DEPOSITO COMUN",
         "BICICLETERO", "ESTACIONAMIENTO BICICLETAS", "CUARTO BICICLETAS"], "comun")

    # Administración y guardias
    add(["PORTERIA EDIFICIO", "GUARDIA", "CASETA GUARDIA", "SALA GUARDIA",
         "OFICINA ADMINISTRACION", "SALA ADMINISTRACION", "GERENCIA EDIFICIO",
         "SALON DE DIRECTORIO", "SALA DE DIRECTORIO EDIFICIO"], "comun")

    # Baño / servicios comunes (no de depto)
    add(["BANO COMUN", "BANO VISITAS EDIFICIO", "SSHH COMUN", "SSHH PISO",
         "SERVICIO HIGIENICO COMUN", "CAMBIADOR COMUN"], "comun")

    # ── VIAL (infraestructura civil urbana chilena) ───────────────────────────
    # Fuentes: SERVIU Metropolitano, MOP Vialidad, Manual Metro Santiago,
    #          EFE Norma Via 2019, MOP Concesiones, Manual Drenaje Vial MOP 2011,
    #          MINVU Vialidad Ciclo-Inclusiva 2025, Manual Señalizacion MOP 2012

    # Calzada / sección transversal (REDEVU MINVU / MOP)
    add(["CALZADA", "PISTA", "PISTA DE RODADO", "CARRIL",
         "CARRIL DERECHO", "CARRIL IZQUIERDO", "CARRIL CENTRAL",
         "CALZADA NORTE", "CALZADA SUR", "CALZADA ORIENTE", "CALZADA PONIENTE",
         "CALZADA PTE", "CALZADA OTE",
         "VIA RAPIDA", "VIA EXPRESA", "VIA TRONCAL", "VIA COLECTORA",
         "VIA LOCAL", "VIA DE SERVICIO",
         "AUTOPISTA", "RUTA", "CAMINO", "CAMINO RURAL", "CAMINO VECINAL",
         "PASAJE VEHICULAR", "CALLEJON",
         "PAVIMENTO", "PAVIMENTO ASFALTICO", "PAVIMENTO FLEXIBLE",
         "PAVIMENTO RIGIDO", "CALZADA DE SERVICIO"], "vial")
    for n in ["1", "2", "3", "4"]:
        add([f"PISTA {n}", f"CARRIL {n}", f"VIA {n}", f"TUBO {n}"], "vial")

    # Pistas especiales
    add(["PISTA DE CIRCULACION", "PISTA EXCLUSIVA BUS", "PISTA EXCLUSIVA TAXI",
         "PISTA REVERSIBLE", "PISTA DE VIRAJE", "PISTA DE ACELERACION",
         "PISTA DE DESACELERACION", "PISTA DE ADELANTAMIENTO",
         "PISTA BICI", "CICLOCARRIL"], "vial")

    # Aceras / ciclovías (SERVIU / MINVU Vialidad Ciclo-Inclusiva 2025)
    add(["VEREDA", "VEREDA PONIENTE", "VEREDA ORIENTE", "VEREDA NORTE", "VEREDA SUR",
         "ACERA", "BANQUETA",
         "CICLOVÍA", "CICLOVIA", "CICLOBANDA", "CICLOPISTA", "CICLOACERA",
         "BERMA", "BERMA PAVIMENTADA", "BERMA DERECHA", "BERMA IZQUIERDA",
         "BERMA DE ESTACIONAMIENTO",
         "ZONA PEATONAL", "PASEO PEATONAL", "PASEO",
         "CALZADA PEATONAL", "SENDA PEATONAL", "SENDA MULTIPROPÓSITO",
         "FAJA DE PLANTACION", "FAJA VERDE",
         "NIVEL DE CALZADA", "NIVEL DE VEREDA",
         "LINEA OFICIAL", "LINEA DE EDIFICACION",
         "PERALTE", "SOBREELEVACION"], "vial")

    # Estacionamiento vial (en calle, diferente de estac. edificio)
    add(["ESTACIONAMIENTO EN LINEA", "ESTACIONAMIENTO EN BATERIA",
         "FRANJA DE ESTACIONAMIENTO VIAL"], "vial")

    # Separadores / medianas
    add(["MEDIANA", "BANDEJON", "BANDEJÓN", "BANDEJON CENTRAL", "BANDEJON LATERAL",
         "SEPARADOR CENTRAL", "SEPARADOR VIAL", "ISLETA", "ISLA",
         "CANTON VIAL"], "vial")

    # Intersecciones / rotondas
    add(["ROTONDA", "GLORIETA", "INTERSECCION", "INTERSECCION A NIVEL",
         "CRUCE", "CRUCE PEATONAL", "PASO PEATONAL", "PASO DE CEBRA",
         "BIFURCACION", "EMPALME", "ENLACE",
         "PASO BAJO NIVEL", "PBN", "PASO SOBRE NIVEL", "PSN",
         "PASO DESNIVEL", "PASO A DESNIVEL", "PASO ELEVADO", "PASO SUPERIOR"], "vial")

    # Cunetas / drenaje vial (SERVIU Metropolitano / Manual Aguas Lluvias)
    add(["CUNETA", "CUNETA HORMIGON", "CUNETA REVESTIDA", "CUNETA SIN REVESTIR",
         "CUNETA TRIANGULAR", "CUNETA TRAPEZOIDAL",
         "CUNETA DE PIE DE TALUD", "CUNETA DE CORONACION",
         "FOSO", "ZANJON", "CANAL DE DRENAJE", "CANAL VIAL",
         "CANAL REVESTIDO", "CANAL DE TIERRA",
         "COLECTOR", "COLECTOR VIAL", "COLECTOR PRINCIPAL", "COLECTOR SECUNDARIO",
         "COLECTOR DE AGUAS LLUVIAS", "COLECTOR CAJON",
         "COLECTOR CAJON DE HORMIGON",
         "SUMIDERO", "SUMIDERO DE REJA", "SUMIDERO TIPO SERVIU",
         "REJILLA DE SUMIDERO",
         "BAJADA DE AGUAS", "BAJADA DE AGUA PLUVIAL", "BAJADA A COLECTOR",
         "DESCARGA PLUVIAL", "DESCOLE",
         "SOLERA", "SOLERA TIPO A", "SOLERA TIPO B", "SOLERA NORMAL",
         "SOLERILLA", "SOLERA DE CONFINAMIENTO"], "vial")

    # Cámaras de drenaje (NCh 1623 / SERVIU)
    add(["CAMARA DE INSPECCION", "CAMARA DE INSPECCION TIPO",
         "POZO DE INSPECCION", "POZO DE VISITA", "POZO DE REGISTRO",
         "CAMARA UNION", "CAMARA DE UNION", "CAMARA DE QUIEBRE",
         "CAMARA DE CAIDA", "CAMARA DE REUNION", "CAMARA REPARTIDORA",
         "CAMARA DE LIMPIEZA", "CAMARA DE REJAS",
         "TAPA DE HORMIGON", "TAPA METALICA", "MARCO Y TAPA",
         "RADIER DE CAMARA",
         "OBRA DE ARTE", "OBRA DE PASO",
         "DISIPADOR DE ENERGIA", "TRAMPA DE SOLIDOS",
         "FOSA DE DECANTACION"], "vial")

    # Túneles carreteros (MOP / Dirección de Vialidad)
    add(["TUNEL", "TÚNEL", "GALERIA", "GALERÍA",
         "PORTAL DE TUNEL", "PORTAL NORTE", "PORTAL SUR",
         "PORTAL PONIENTE", "PORTAL ORIENTE",
         "PORTAL DE ENTRADA", "PORTAL DE SALIDA",
         "TUBO PONIENTE", "TUBO ORIENTE",
         "TUNEL CARRETERO", "TUNEL VIAL", "TUNEL PEATONAL",
         "BOCA DE TUNEL", "EMBOQUILLADO", "EMBOCADURA",
         "GALERIA DE BYPASS", "GALERIA DE CONEXION",
         "GALERIA DE EVACUACION", "GALERIA DE RESCATE",
         "GALERIA DE SERVICIO", "GALERIA DE EMERGENCIA",
         "NICHO DE EMERGENCIA", "NICHO SOS",
         "NICHO DE EXTINTOR", "NICHO DE TELEFONO", "NICHO DE ESCAPE",
         "CAMARA DE VENTILACION", "CAMARA DE VENTILACION LONGITUDINAL",
         "POZO DE VENTILACION", "SALA DE VENTILADORES",
         "CAMARA DE BOMBEO TUNEL", "CAMARA DE CONTROL TUNEL",
         "CENTRO DE CONTROL DE TUNEL",
         "ENSANCHE DE TUNEL", "APARTADERO DE TUNEL",
         "ZONA DE ESCAPE", "VIA DE ESCAPE",
         "ZONA DE SEGURIDAD TUNEL", "ACERA DE TUNEL",
         "REFUGIO DE EMERGENCIA", "REFUGIO"], "vial")

    # Elementos estructurales de túneles
    add(["BOVEDA", "BÓVEDA", "CLAVE DE LA BOVEDA",
         "HASTIAL", "HASTIAL IZQUIERDO", "HASTIAL DERECHO",
         "CONTRABOVEDA", "SOLERA DE TUNEL",
         "SOSTENIMIENTO", "SHOTCRETE", "HORMIGON PROYECTADO",
         "PERNO DE ROCA", "BULON DE ANCLAJE", "MALLA ELECTROSOLDADA TUNEL",
         "ARCO METALICO", "CERCHA METALICA",
         "REVESTIMIENTO DEFINITIVO", "REVESTIMIENTO PRIMARIO",
         "MEMBRANA IMPERMEABILIZANTE", "IMPERMEABILIZACION DE TUNEL",
         "DRENAJE DE TUNEL", "COLECTOR DE TUNEL",
         "CAMARA DE RETAGUARDIA", "CAMARA DE AVANCE"], "vial")

    # Puentes / estructuras viales (MOP)
    add(["PUENTE", "VIADUCTO", "PASO INFERIOR", "PASO DESNIVEL",
         "TABLERO", "TABLERO DE PUENTE", "LOSA DE PUENTE",
         "MURO DE ALA", "MURO TESTA", "ESTRIBO",
         "PILA", "PILON", "APOYO DE PUENTE",
         "BARANDADO", "BARANDA VIAL"], "vial")

    # Subestructura de puentes
    add(["ESTRIBO IZQUIERDO", "ESTRIBO DERECHO",
         "PILA TIPO COLUMNA", "PILA MARTILLO", "PILA CIRCULAR", "PILA RECTANGULAR",
         "ZAPATA DE PUENTE", "LOSA DE CIMENTACION",
         "PILOTES DE HORMIGON", "PILOTES BARRENADOS",
         "CABEZAL DE PILOTES", "ALA DEL ESTRIBO", "MURO TESTERO",
         "LOSA DE APROXIMACION", "LOSA DE TRANSICION",
         "VIGA DE CORONAMIENTO PUENTE"], "vial")

    # Superestructura / tablero de puentes
    add(["VIGA PRINCIPAL", "VIGA T PREFABRICADA", "VIGA I PRETENSADA",
         "VIGA CAJON", "VIGA TRANSVERSAL", "VIGA DE BORDE",
         "DIAFRAGMA", "DIAFRAGMA INTERMEDIO", "DIAFRAGMA DE EXTREMO",
         "LOSA DE TABLERO", "BARANDA DE HORMIGON", "PARAPETO PUENTE",
         "JUNTA DE DILATACION", "APOYO ELASTOMERICO", "NEOPRENO DE APOYO",
         "CARPETA ASFALTICA DE PUENTE", "IMPERMEABILIZACION DE TABLERO",
         "SUMIDERO DE PUENTE", "TUBO BAJANTE PUENTE"], "vial")

    # Muros de contención / taludes
    add(["MURO DE CONTENCION", "MURO DE CONTENCIÓN",
         "MURO DE SOSTENIMIENTO", "MURO PANTALLA",
         "MURO DE GRAVEDAD", "MURO EN VOLADIZO",
         "MURO CON CONTRAFUERTES", "MURO DE MAMPOSTERIA",
         "MURO DE PIEDRA", "MURO SECO",
         "TALUD", "TALUD DE CORTE", "TALUD DE RELLENO",
         "TERRAPLÉN", "TERRAPLEN", "BANQUETA DE TALUD"], "vial")

    # Contención con técnicas especiales
    add(["MURO DE GAVIONES", "GAVION", "COLCHON DE GAVIONES",
         "PANTALLA DE PILOTES", "PARED BERLIN", "MURO BERLINES",
         "TABLESTACAS", "TABLESTACAS DE ACERO",
         "MICROPILOTES", "CORTINA DE MICROPILOTES",
         "SOIL NAILING", "PERNO DE SUELO",
         "ANCLAJE ACTIVO", "ANCLAJE PASIVO", "TIRANTE DE ANCLAJE",
         "ENTIBACION", "TABLON DE ENTIBACION",
         "ESCOLLERA", "MURO DE ESCOLLERA",
         "MURO DE TIERRA ARMADA", "SUELO REFORZADO", "GEOMALLA",
         "GEOTEXTIL", "GEODREN",
         "DREN HORIZONTAL", "DREN SUBHORIZONTAL", "TUBO DREN",
         "ZANJA DRENANTE"], "vial")

    # Capas de pavimento (SERVIU Metropolitano / MOV SERVIU 2018)
    add(["CARPETA ASFALTICA", "MEZCLA ASFALTICA EN CALIENTE",
         "ASFALTO MODIFICADO EN CALIENTE",
         "CAPA DE RODADO", "CAPA DE RODADURA", "CAPA DE DESGASTE",
         "BASE GRANULAR", "BASE ESTABILIZADA",
         "BASE TRATADA CON CEMENTO",
         "SUB-BASE GRANULAR", "SUBRASANTE", "SUBRASANTE MEJORADA",
         "MATERIAL SELECCIONADO", "RELLENO ESTRUCTURAL",
         "RIEGO DE IMPRIMACION", "RIEGO DE LIGA", "RIEGO DE ADHERENCIA",
         "IMPRIMACION ASFALTICA", "CAPA IMPRIMACION",
         "SELLO ASFALTICO", "SELLO DE GRIETAS", "MICROPAVIMENTO",
         "LECHADA ASFALTICA", "TRATAMIENTO SUPERFICIAL BICAPA",
         "PAVIMENTO FLEXIBLE", "PAVIMENTO GRANULAR",
         "LOSA DE HORMIGON CALZADA", "BARRAS PASAJUNTAS",
         "JUNTA DE CONTRACCION VIAL", "JUNTA DE EXPANSION VIAL",
         "AFIRMADO GRANULAR", "CAMINO RIPIO", "RIPIO COMPACTADO",
         "ESPALDON", "BERMA GRANULAR", "CAMINO LATERAL"], "vial")

    # Conservacion vial y mantenimiento
    add(["RECARPETEO", "BACHEO", "PARCHADO",
         "SELLO DE FISURAS", "SELLO DE GRIETAS",
         "MICROPAVIMENTO", "LECHADA ASFALTICA",
         "CONSERVACION PERIODICA", "MANTENIMIENTO VIAL",
         "REPOSICION CARPETA", "FRESADO ASFALTICO"], "vial")

    # Vereda / baldosas SERVIU
    add(["BALDOSA PODO-TACTIL", "BALDOSA DE ALERTA", "BALDOSA DE GUIA",
         "LOSETA PODO-TACTIL", "RAMPA PEATONAL",
         "RAMPA PARA DISCAPACITADOS", "REBAJE DE SOLERA", "PISO TACTIL",
         "HORMIGON POBRE VEREDA", "CAMA DE ARENA", "CAMA DE RIPIO",
         "CICLOVIA", "CICLOBANDA", "CICLOPISTA", "VIA CICLISTA",
         "SENDA CICLISTA", "SENDA PEATONAL"], "vial")

    # Drenaje subterraneo y subdrenaje
    add(["SUBDREN TRANSVERSAL", "SUBDREN LONGITUDINAL",
         "DRENE LONGITUDINAL", "DREN SUBTERRANEO",
         "TUBERIA HDPE", "TUBERIA CORRUGADA",
         "CONTRACUNETA", "CUNETA DE PIE", "CUNETA CORONAMIENTO",
         "BAJADA DE AGUA", "CANAL DE CORONACION",
         "ZANJA DRENANTE", "GEODREN PLANO", "CAMA DE ARENA TUBERIA"], "vial")

    # Señaletica de conservacion
    add(["BALIZAS", "BALIZA RETROREFLECTANTE", "HITO KILOMETRICO",
         "DELINEADOR VIAL", "OJO DE GATO", "TACHAS RETROREFLECTANTES",
         "LINEAS CONTINUAS", "LINEAS DISCONTINUAS", "MARCAS VIALES",
         "LINEAS DE EJE", "DEMARCACION HORIZONTAL",
         "IMBORNAL", "REJILLA CAPTACION", "SUMIDERO DE CALZADA"], "vial")

    # Salas tecnicas en infraestructura (metro, tuneles, vial) — no son recintos habitables
    add(["SALA SER", "SALA SER METRO", "SALA SER ESTACION",
         "SALA ELECTRICA METRO", "SALA ELECTRICA TUNEL",
         "SALA DE CONTROL TUNEL", "SALA DE CONTROL METRO", "SALA DE BOMBAS TUNEL",
         "SALA DE VENTILACION", "SALA DE EMERGENCIA TUNEL",
         "SALA DE MAQUINAS METRO", "SALA DE EQUIPOS METRO",
         "SALA TECNICA METRO", "SALA TECNICA TUNEL", "SALA TECNICA VIAL",
         "LOCAL TECNICO METRO",
         "SALA CCI", "SALA CCI METRO", "CCI METRO",
         "SALA DE TELECOMUNICACIONES METRO", "SALA TELECOMUNICACIONES VIAL",
         "SALA DE VENTILADORES", "SALA VENTILADORES TUNEL",
         "PASAJE VEHICULAR", "PASO VEHICULAR TUNEL",
         "DREN SUBTERRANEO", "SISTEMA DRENAJE SUBTERRANEO",
         "AREA DE SERVICIO VIAL", "AREA SERVICIO CARRETERA",
         "FAJA VERDE VIAL", "FAJA VERDE CENTRAL", "FAJA VERDE LATERAL",
         "TRAMO SUBTERRANEO VIAL", "TRAMO SUBTERRANEO METRO",
         "SALA TECNICA ESTACION", "SALA OPERACIONES METRO",
         "SALA DE CONTROL VIAL", "CENTRO DE CONTROL TRAFICO"], "vial")

    # Señalización / apoyo vial
    add(["ÁREA DE SERVICIO", "AREA DE SERVICIO",
         "PLAZA DE PEAJE", "CASETA DE PEAJE",
         "ESTACION DE PEAJE", "PÓRTICO", "PORTICO",
         "AREA DE DESCANSO", "MIRADOR",
         "SALA DE CONTROL VIAL", "CASETA DE CONTROL"], "vial")

    # Metro Santiago — andenes y zonas operacionales (Manual Metro 2016 / L7 EIA)
    add(["ANDÉN METRO", "ANDÉN", "ANDEN", "ANDEN METRO",
         "ANDÉN PONIENTE", "ANDÉN ORIENTE",
         "ANDÉN LATERAL", "ANDÉN CENTRAL", "PLATAFORMA METRO",
         "MEZZANINE", "MESANINA", "NIVEL MEZZANINE", "NIVEL ANDEN",
         "NIVEL ACCESO METRO", "PUENTE MESANINA",
         "ZONA PAGADA", "ZONA NO PAGADA",
         "ACCESO METRO PONIENTE", "ACCESO METRO ORIENTE",
         "GALERIA DE ACCESO METRO", "POZO DE ACCESO METRO",
         "PIQUE DE VENTILACION METRO", "CAMARA DE VENTILACION METRO",
         "SALA SER", "SALA SER METRO", "SALA SER ESTACION", "SER ESTACION",
         "SALA SER PONIENTE", "SALA SER ORIENTE", "SALA ELECTRICA METRO",
         "SER METRO", "SUBESTACION RECTIFICADORA", "SUBESTACION DE RECTIFICACION",
         "SALA CCI", "SALA CCI METRO", "CCI METRO",
         "SALA DE TELECOMUNICACIONES METRO",
         "SALA DE CLIMATIZACION METRO", "SALA DE TABLEROS ELECTRICOS METRO",
         "TUNEL METRO", "TUNEL FERROVIARIO", "VIA FERREA",
         "ESTACION METRO", "TRAMO SUBTERRANEO", "TRAMO ELEVADO",
         "GALERIA AUXILIAR", "PIQUE DE CONSTRUCCION",
         "INTERESTACION", "PLATAFORMA FERROVIARIA"], "vial")

    # Vía férrea / ferroviario
    add(["TROCHA", "BALASTRO", "TRAVIESA DE HORMIGON",
         "VIA EN PLACA", "LOSA FLOTANTE FERROVIARIA",
         "TERCER RIEL", "CARRIL CONDUCTOR",
         "ZONA DE MANTENIMIENTO VIA", "CAMARA DE CABLES",
         "TRINCHERA", "ZANJA DE CABLES FERROVIARIA"], "vial")

    # ── EFE / Ferrocarriles del Estado — terminología planos (Norma Via EFE 2019) ──
    add(["ANDEN FERROVIARIO", "ANDEN BAJO", "ANDEN ALTO",
         "ANDEN ESTACION EFE", "BORDE ANDÉN FERROVIARIO",
         "DESVIO FERROVIARIO", "DESVIO SIMPLE", "DESVIO DOBLE",
         "CAMBIO DE VIA", "AGUJA FERROVIARIA",
         "PASO A NIVEL", "PASO A NIVEL CON BARRERAS",
         "CRUCE A NIVEL FERROVIARIO", "BARRERAS NIVEL",
         "BADÉN FERROVIARIO",
         "ZONA RESGUARDO ANDÉN", "ZONA SEGURIDAD VIA",
         "DEPOSITO MATERIALES VIA", "ZONA MANTENIMIENTO VIA EFE",
         "COCHERA FERROVIARIA", "TALLER VIA",
         "SEÑAL FERROVIARIA", "SEÑAL LATERAL VIA",
         "ACCESO ANDEN FERROVIARIO"], "vial")

    # ── Semáforos / señalética activa (Manual Señalización MOP 2012) ──────────
    add(["SEMAFORO", "SEMÁFORO", "SEMAFORO VEHICULAR", "SEMAFORO PEATONAL",
         "SEMAFORO LED", "CABEZA SEMAFORO",
         "POSTE SEMAFORO", "BRAZO SEMAFORO", "MÁSTIL SEMÁFORO",
         "CONTROLADOR SEMAFORICO", "CONTROLADOR DE TRAFICO",
         "LAZO INDUCTIVO", "DETECTOR DE TRAFICO", "DETECTOR PEATONAL",
         "CAMARA FOTORRADAR", "CAMARA VELOCIDAD",
         "PANEL DE MENSAJES VARIABLE", "PMV", "PANEL VARIABLE",
         "PORTAL DE MENSAJES", "SEÑAL VARIABLE",
         "SEÑAL REGLAMENTARIA", "SENAL REGLAMENTARIA",
         "SEÑAL PREVENTIVA", "SENAL PREVENTIVA",
         "SEÑAL INFORMATIVA", "SENAL INFORMATIVA",
         "SEÑAL DIRECCIONAL", "SENAL TURISTICA",
         "POSTE SEÑAL VIAL", "SOPORTE SEÑAL", "FUNDACION SEÑAL",
         "CARTEL VIAL", "CARTEL NOMENCLATURA",
         "PLACA NOMBRE CALLE", "PLACA NUMERO DOMICILIO VIAL"], "vial")

    # ── Concesiones autopistas (MOP Concesiones / Dirección de Vialidad) ─────
    add(["CANALETA DE PEAJE", "CANALETA VIA LIBRE", "CANALETA MIXTA",
         "CANALETA TELEPAGO", "CANALETA MANUAL",
         "ISLA DE PEAJE", "CABINA DE PEAJE", "CASETA COBRO",
         "PÓRTICO DE PEAJE", "PORTICO ESTRUCTURA",
         "PLAZA DE TOLL", "AREA DE TOLL",
         "RAMAL DE ACCESO", "RAMAL DE SALIDA",
         "BRAZO DE ENLACE", "LOOP DE ENLACE",
         "DISTRIBUIDORA", "VIA DISTRIBUIDORA", "PISTA DISTRIBUIDORA",
         "RETORNO VIAL", "RETORNO AUTORIZADO",
         "BANDA RUGOSA", "RESALTO VIAL",
         "BARRERA ELECTRONICA", "ARCO TELEPEAJE",
         "AREA DE DESCANSO AUTOPISTA", "BAHIA DE BUSES",
         "BAHIA DE TAXIS", "BAHIA DE ESTACIONAMIENTO"], "vial")

    # ── Obras de arte menor — alcantarillas (Manual Drenaje Vial MOP 2011) ───
    add(["CAJON HORMIGON", "CAJON SIMPLE", "CAJON DOBLE", "CAJON TRIPLE",
         "CAJON PREFABRICADO", "CAJON 1.5x1.5", "CAJON 2x2",
         "ALCANTARILLA CIRCULAR", "ALCANTARILLA OVOIDEA",
         "ALCANTARILLA METALICA CORRUGADA", "ALCANTARILLA ARMCO",
         "CABEZAL DE DESCARGA", "CABEZAL ALETA", "CABEZAL RECTO",
         "BOCA DE DESCARGA", "DESCARGA LIBRE",
         "LOSA SOBRE ALCANTARILLA", "RELLENO SOBRE ALCANTARILLA",
         "EMBOCADURA ALCANTARILLA", "ALETÓN DE ALCANTARILLA"], "vial")

    # ── Movimiento de tierras — detalle MOP Vol.3 Cap.3.500 ──────────────────
    add(["CORTE NETO", "PRESTAMO PROPIO", "PRESTAMO EXTERNO",
         "DEPOSITO DE EXCEDENTES", "BOTADERO CONTROLADO",
         "RELLENO COMUN", "RELLENO SELECCIONADO", "RELLENO CONTROLADO",
         "COMPACTACION ESPECIAL", "ESCARPE FORESTAL",
         "PERFILADO TALUD", "RECONFORMACION TALUD",
         "ROCE Y LIMPIEZA", "ROCE FORESTAL",
         "PLATAFORMA DE TRABAJO PROVISIONAL", "PLATAFORMA DE TRABAJO",
         "DESVIO PROVISIONAL", "PASO PROVISORIO",
         "CAMINO PROVISORIO", "ACCESO PROVISIONAL"], "vial")

    # ── Infraestructura ciclista — MINVU Vialidad Ciclo-Inclusiva 2025 ───────
    add(["CICLOBANDA PROTEGIDA", "CICLOVÍA BIDIRECCIONAL", "CICLOVÍA UNIDIRECCIONAL",
         "CRUCE CICLOVIAL", "SEMÁFORO CICLISTA",
         "ESTACIONAMIENTO BICICLETAS VIAL", "BICICLETERO VIAL",
         "ZONA DE ESPERA CICLISTA", "CAJA DE ESPERA CICLISTA",
         "APARCA BICICLETAS", "SOPORTE BICICLETAS VIAL",
         "CICLOINFRAESTRUCTURA", "SENDA COMPARTIDA"], "vial")

    # ── Protección fluvial y costera (MOP / DGA) ──────────────────────────────
    add(["PROTECCION DE RIBERA", "DEFENSA FLUVIAL", "MURO RIBERA",
         "ENROCADO RIBERA", "ESCOLLERA RIBERA",
         "ZAMPEADO HORMIGON", "ZAMPEADO PIEDRA",
         "REVESTIMIENTO CANAL NATURAL", "CORRECCIÓN TORRENCIAL",
         "GAVION DE RIBERA", "COLCHON RENO RIBERA",
         "DIQUE DE CONTENCION", "DIQUE DE RETENCION",
         "SEDIMENTADOR", "TRAMPA DE SEDIMENTOS",
         "OBRA DE TOMA", "OBRA DE ENTREGA"], "vial")

    # ── ELÉCTRICO (infraestructura LAT subterránea — piques + túnel liner) ──────
    # Piques circulares de acceso (Ø4000mm interior, Ø4200mm fundación)
    add(["PIQUE 1", "PIQUE 2", "PIQUE 3", "PIQUE 4", "PIQUE 5",
         "PIQUE 6", "PIQUE 7", "PIQUE 8", "PIQUE 9",
         "PIQUE SS VITACURA", "PIQUE SS PROVIDENCIA",
         "PIQUE TIPICO", "PIQUE TÍPICO",
         "PIQUE CIRCULAR", "PIQUE CIRCULAR O4000",
         "PIQUE ACCESO", "PIQUE ZONA TABLEROS",
         "PIQUE LAT", "PIQUE ELECTRICO", "PIQUE ELÉCTRICO",
         "POZO ACCESO ELECTRICO", "SHAFT ELECTRICO"], "electrico")

    # Túnel liner (Ø2210mm interior, pipe jacking / TBM)
    add(["TUNEL LINER", "TUNNEL LINER", "LINER TUNEL",
         "LINER O2210", "LINER 2210", "LINER Ø2210",
         "SECCION LINER", "SECCION TUNEL LINER",
         "TUNEL LAT", "GALERIA ELECTRICA", "GALERÍA ELÉCTRICA",
         "GALERIA LAT", "DUCTO SUBTERRANEO LAT",
         "TRAMO TUNEL 1", "TRAMO TUNEL 2", "TRAMO LINER",
         "TRAMO 1 P1-P2", "TRAMO 2 P2-P3"], "electrico")

    # Plataformas y equipamiento interno de piques
    add(["PLATAFORMA DE DESCANSO", "PLATAFORMA TECNICA", "PLATAFORMA ELECTRICA",
         "PLATAFORMA 1", "PLATAFORMA 2", "PLATAFORMA 3",
         "PLATAFORMA 4", "PLATAFORMA 5", "PLATAFORMA 6",
         "PLATAFORMA 7", "PLATAFORMA 8",
         "ESCALERA GATERA", "ESCALA GATERA", "ESCALA VERTICAL",
         "ANILLO INFERIOR", "ANILLO SUPERIOR", "ANILLO ESTRUCTURAL",
         "ANILLO LINER PIQUE"], "electrico")

    # Salas y equipos eléctricos en piques (SS/EE y sala de control)
    add(["SALA TABLEROS", "ZONA TABLEROS", "ZONA TDF",
         "TDF 1", "TDF 2", "TDF 3", "TDF VIT", "TDF PROV",
         "SALA TDF", "TABLERO DE DISTRIBUCION",
         "SALA VENTILACION", "CUARTO VENTILACION",
         "FAN PIQUE", "VENTILADOR TUNEL",
         "SALA BOMBAS PIQUE", "PLANTA ELEVADORA PIQUE",
         "SUBESTACION VITACURA", "SUBESTACION PROVIDENCIA",
         "SS VITACURA", "SS PROVIDENCIA",
         "SALA SER LAT", "SALA CONTROL LAT"], "electrico")

    # Ventilación de galería eléctrica (jet fans + extractores)
    # IDs FAN1..FAN23 vienen del proyecto Vitacura (STM38109 Tabla 4.2)
    add(["JET FAN", "VENTILADOR JET FAN", "FAN TUNEL",
         "VENTILADOR IMPULSO GALERIA LAT", "JET FAN GALERIA",
         "EXTRACTOR GALERIA LAT", "VENTILADOR EXTRACTOR TUNEL CABLES",
         "EQUIPO VENTILACION GALERIA LAT", "SISTEMA VENTILACION LAT",
         "FAN1", "FAN5", "FAN12", "FAN23",
         "FAN.01", "FAN.12", "FAN.23"], "electrico")

    # Elementos estructurales y de obra civil propios del sistema
    add(["BROCAL DEFINITIVO", "BROCAL TEMPORAL", "BROCAL PIQUE",
         "RADIER PIQUE", "RADIER TUNEL LINER",
         "LOSA ANILLO FONDO", "REFUERZO APERTURA PIQUE",
         "DREN PIQUE", "CAMARA CONEXION AT",
         "CAMARA CONEXION ALTA TENSION",
         "COBERTURA PIQUE", "TAPA PIQUE",
         "ESTRUCTURA SOPORTE CABLES LAT",
         "CABLE AT SUBTERRANEO", "CABLE 110KV SUBTERRANEO",
         "LAT 2X110KV", "LINEA 110KV SUBTERRANEA"], "electrico")

    # ── Geotecnia de obra vial — sondajes y tratamientos (INN / MOP) ─────────
    add(["MICROPILOTE", "MICROPILOTES CIMENTACION", "MICROPILOTES CONTENCION",
         "PILOTE PERFORADO", "PILOTE CENTRIFUGADO", "PILOTE BARRENADO",
         "CALICATA", "SONDAJE GEOTECNICO",
         "PIEZOMETRO", "INCLINOMETRO VIAL",
         "INYECCION DE CEMENTO", "JET GROUTING",
         "MEJORAMIENTO SUELO DINAMICO", "COMPACTACION DINAMICA",
         "COLCHON GRANULAR", "COLCHON DRENANTE"], "vial")

    return datos


def construir_modelo() -> Pipeline:
    return Pipeline([
        ("feat", FeatureUnion([
            ("char", TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(2, 6),
                lowercase=False,
                sublinear_tf=True,
            )),
            ("word", TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 2),
                lowercase=False,
                sublinear_tf=True,
            )),
        ])),
        ("clf", LogisticRegression(
            max_iter=2000,
            C=10.0,
            class_weight="balanced",
            solver="lbfgs",
        )),
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", action="store_true", help="Solo métricas CV, no guarda pkl")
    parser.add_argument("--tune", action="store_true", help="GridSearchCV de hiperparámetros (lento)")
    args = parser.parse_args()

    datos_raw = _generar_dataset()
    # Deduplica: primer label gana; reporta conflictos cross-label
    seen: dict[str, str] = {}
    datos = []
    for nombre, cat in datos_raw:
        if nombre not in seen:
            seen[nombre] = cat
            datos.append((nombre, cat))
        elif seen[nombre] != cat:
            print(f"  WARN conflicto: {nombre!r} era {seen[nombre]!r}, ignorando {cat!r}")
    X = [nombre for nombre, _ in datos]
    y = [cat for _, cat in datos]

    clases = ["comun", "electrico", "exterior", "humedo", "seco", "vial"]

    print(f"Dataset: {len(datos)} ejemplos")
    for cat in clases:
        n = y.count(cat)
        print(f"  {cat:<10} {n:>4} ({n/len(y)*100:.0f}%)")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    if args.tune:
        from sklearn.model_selection import GridSearchCV
        param_grid = {
            "clf__C": [0.5, 1.0, 5.0, 10.0],
            "feat__char__ngram_range": [(2, 4), (2, 5), (2, 6)],
        }
        modelo = construir_modelo()
        gs = GridSearchCV(modelo, param_grid, cv=cv, scoring="accuracy", n_jobs=-1, verbose=1)
        gs.fit(X, y)
        print(f"\nMejores parámetros: {gs.best_params_}")
        print(f"Mejor CV accuracy:  {gs.best_score_:.4f}")
        return

    modelo = construir_modelo()
    scores = cross_val_score(modelo, X, y, cv=cv, scoring="accuracy")
    print(f"\nCV accuracy: {scores.mean():.4f} ± {scores.std():.4f}")

    y_cv = cross_val_predict(modelo, X, y, cv=cv)
    print("\nConfusion matrix (CV):")
    cm = confusion_matrix(y, y_cv, labels=clases)
    print(f"{'':>10}  " + "  ".join(f"{c[:5]:>6}" for c in clases))
    for i, c in enumerate(clases):
        row = "  ".join(f"{cm[i,j]:>6}" for j in range(len(clases)))
        err = cm[i].sum() - cm[i, i]
        pct = err / cm[i].sum() * 100
        print(f"{c:>10}  {row}   err={err}/{cm[i].sum()} ({pct:.0f}%)")

    modelo.fit(X, y)
    y_pred = modelo.predict(X)
    print("\nClasificación sobre dataset completo:")
    print(classification_report(y, y_pred, target_names=clases))

    if not args.eval:
        with open(PKL_PATH, "wb") as f:
            pickle.dump(modelo, f, protocol=4)
        kb = PKL_PATH.stat().st_size // 1024
        print(f"Modelo guardado: {PKL_PATH}  ({kb} KB)")

    _validar_edge_cases(modelo)


def _validar_edge_cases(modelo: Pipeline) -> None:
    casos = [
        # Residencial
        ("KITCHENETTE", "humedo"),
        ("SH", "humedo"),
        ("SSHH", "humedo"),
        ("WET BAR", "humedo"),
        ("COCINA-LAV", "humedo"),
        ("BOUDOIR", "seco"),
        ("HOME OFFICE", "seco"),
        ("WALK-IN", "seco"),
        ("DORM.PRINCIPAL", "seco"),
        ("QUINCHO", "exterior"),
        ("SOLARIUM", "exterior"),
        ("HALL DISTRIBUIDOR", "comun"),
        ("SHAFT", "comun"),
        ("SUM", "comun"),
        # Civil / vial — básico
        ("CALZADA", "vial"),
        ("PISTA 1", "vial"),
        ("VEREDA", "vial"),
        ("CICLOVÍA", "vial"),
        ("TUNEL", "vial"),
        ("PORTAL NORTE", "vial"),
        ("NICHO DE EMERGENCIA", "vial"),
        ("ROTONDA", "vial"),
        ("CUNETA", "vial"),
        ("PUENTE", "vial"),
        ("MURO DE CONTENCION", "vial"),
        ("PLAZA DE PEAJE", "vial"),
        ("ANDEN METRO", "vial"),
        ("TUNEL METRO", "vial"),
        # Civil / vial — terminología chilena oficial
        ("CAMARA DE INSPECCION", "vial"),
        ("POZO DE VISITA", "vial"),
        ("COLECTOR DE AGUAS LLUVIAS", "vial"),
        ("SUMIDERO TIPO SERVIU", "vial"),
        ("SOLERA TIPO A", "vial"),
        ("SOLERILLA", "vial"),
        ("BANDEJÓN CENTRAL", "vial"),
        ("CICLOBANDA", "vial"),
        ("VIA EXPRESA", "vial"),
        ("PISTA EXCLUSIVA BUS", "vial"),
        ("PORTAL PONIENTE", "vial"),
        ("BOVEDA", "vial"),
        ("HASTIAL DERECHO", "vial"),
        ("SHOTCRETE", "vial"),
        ("ESTRIBO IZQUIERDO", "vial"),
        ("LOSA DE TABLERO", "vial"),
        ("DIAFRAGMA INTERMEDIO", "vial"),
        ("MURO DE GAVIONES", "vial"),
        ("MICROPILOTES", "vial"),
        ("SOIL NAILING", "vial"),
        ("GEOTEXTIL", "vial"),
        ("CARPETA ASFALTICA", "vial"),
        ("BASE GRANULAR", "vial"),
        ("SUB-BASE GRANULAR", "vial"),
        ("RIEGO DE IMPRIMACION", "vial"),
        ("BALDOSA PODO-TACTIL", "vial"),
        ("RAMPA PEATONAL", "vial"),
        ("SALA SER", "vial"),
        ("NIVEL MEZZANINE", "vial"),
        ("ZONA PAGADA", "vial"),
        ("TRAMO SUBTERRANEO", "vial"),
        ("BALASTRO", "vial"),
        ("TRAVIESA DE HORMIGON", "vial"),
        ("GALERIA DE EVACUACION", "vial"),
        ("CAMARA DE VENTILACION LONGITUDINAL", "vial"),
        ("TUBO PONIENTE", "vial"),
    ]
    print("\nEdge cases:")
    ok = errores = 0
    for nombre, esperado in casos:
        n = _norm(nombre)
        pred = modelo.predict([n])[0]
        proba = modelo.predict_proba([n]).max()
        status = "✓" if pred == esperado else "✗"
        if pred == esperado:
            ok += 1
        else:
            errores += 1
        print(f"  {status} {nombre:<28} → {pred:<10} ({proba:.2f})  esperado: {esperado}")
    print(f"\n  {ok}/{ok+errores} edge cases correctos")


if __name__ == "__main__":
    main()
