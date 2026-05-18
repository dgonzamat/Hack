#!/usr/bin/env python3
"""
Entrena clasificador ML de recintos: húmedo / seco / exterior / común.

Dataset sintético ~1800 nombres típicos de construcción chilena.
Modelo: TF-IDF (char n-grams 2-5) + LogisticRegression.
Salida: clasificador_recintos.pkl (<200 KB)

Uso:
    python train_clasificador.py           # entrena + guarda pkl
    python train_clasificador.py --eval    # métricas CV sin guardar
"""

import argparse
import pickle
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

PKL_PATH = Path(__file__).parent / "clasificador_recintos.pkl"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.upper().replace("-", " ").replace("/", " ")).strip()


def _generar_dataset() -> list[tuple[str, str]]:
    datos: list[tuple[str, str]] = []

    def add(nombres: list[str], cat: str) -> None:
        for n in nombres:
            datos.append((_norm(n), cat))

    # ── HÚMEDO ───────────────────────────────────────────────────────────────
    add(["BAÑO", "WC", "TOILET", "DUCHA"], "humedo")
    for base in ["BAÑO", "WC", "BANO"]:
        for n in ["1", "2", "3", "4"]:
            add([f"{base} {n}", f"{base}{n}"], "humedo")
    for q in ["PRINCIPAL", "SUITE", "COMPLETO", "SOCIAL", "SERVICIO", "VISITAS",
              "COMPARTIDO", "DUCHA", "TINA", "MEDIO", "MASTER", "EN SUITE"]:
        add([f"BAÑO {q}", f"BANO {q}", f"WC {q}"], "humedo")

    add(["COCINA", "KITCHENETTE", "COCINETA", "KITCHEN", "COCINA AMERICANA",
         "COCINA ABIERTA", "COCINA SEMI-ABIERTA", "COCINA INTEGRAL",
         "ANTECOCINA", "PANTRY", "WET BAR", "BAR MOJADO", "ISLA COCINA",
         "COCINA COMEDOR", "COCINA LIVING COMEDOR"], "humedo")

    add(["LOGIA", "LOGIA DE SERVICIO", "LOGIA SERVICIO",
         "LAVANDERIA", "LAVANDERÍA", "LAVAND.", "LAVAD.",
         "ZONA DE LAVADO", "ZONA LAVADO", "AREA DE LAVADO",
         "CUARTO LAVADO", "PIEZA DE LAVADO", "PATIO LAVADO",
         "CUARTO DE SERVICIO HUMEDO"], "humedo")

    add(["SH", "SSHH", "S.H.", "S.S.H.H.", "SS.HH.", "SS HH",
         "SERV HIG", "SERVICIO HIGIENICO", "SERVICIO HIGIÉNICO",
         "SERV. HIG."], "humedo")

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
         "ENTRADA", "ACCESO", "INGRESO"], "comun")

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
         "SALA MULTIUSO", "SUM", "SALA DE USO MULTIPLE",
         "BODEGA COMUN", "BODEGA COMÚN",
         "ESTACIONAMIENTO", "ESTACIONAMIENTO VISITAS",
         "CUARTO INSTALACIONES", "SALA TECNICA", "SALA MÁQUINAS",
         "CUARTO ELECTRICO", "SALA ELECTRICA"], "comun")

    return datos


def construir_modelo() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 5),
            lowercase=False,
            sublinear_tf=True,
        )),
        ("clf", LogisticRegression(
            max_iter=1000,
            C=1.0,
            class_weight="balanced",
            solver="lbfgs",
        )),
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", action="store_true", help="Solo métricas CV, no guarda pkl")
    args = parser.parse_args()

    datos = _generar_dataset()
    X = [nombre for nombre, _ in datos]
    y = [cat for _, cat in datos]

    print(f"Dataset: {len(datos)} ejemplos")
    for cat in ("humedo", "seco", "exterior", "comun"):
        n = y.count(cat)
        print(f"  {cat:<10} {n:>4} ({n/len(y)*100:.0f}%)")

    modelo = construir_modelo()

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(modelo, X, y, cv=cv, scoring="accuracy")
    print(f"\nCV accuracy: {scores.mean():.4f} ± {scores.std():.4f}")

    modelo.fit(X, y)
    y_pred = modelo.predict(X)
    print("\nClasificación sobre dataset completo:")
    print(classification_report(y, y_pred, target_names=["comun", "exterior", "humedo", "seco"]))

    if not args.eval:
        with open(PKL_PATH, "wb") as f:
            pickle.dump(modelo, f, protocol=4)
        kb = PKL_PATH.stat().st_size // 1024
        print(f"Modelo guardado: {PKL_PATH}  ({kb} KB)")

    # Validar edge cases críticos
    _validar_edge_cases(modelo)


def _validar_edge_cases(modelo: Pipeline) -> None:
    casos = [
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
