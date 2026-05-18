# Makefile — tareas frecuentes del proyecto cubicador

.PHONY: train train-eval train-tune test lint demo-metro demo-ruta help

## Entrenar modelo con dataset actual y guardar pkl
train:
	python train_clasificador.py

## Evaluar accuracy CV sin guardar pkl
train-eval:
	python train_clasificador.py --eval

## GridSearchCV para afinar hiperparámetros (lento ~5min)
train-tune:
	python train_clasificador.py --tune

## Ejecutar suite de tests
test:
	python -m pytest test_cubicador.py -q

## Lint (errores críticos)
lint:
	python -m ruff check cubicador.py presupuesto.py excel.py train_clasificador.py \
	  --select E9,F63,F7,F82,PLE,YTT
	codespell cubicador.py train_clasificador.py presupuesto.py excel.py

## Demo estación metro tipo L7
demo-metro:
	python demo_metro.py

## Demo ruta vial (si existe)
demo-ruta:
	python demo_ruta1.py 2>/dev/null || echo "[!] demo_ruta1.py no encontrado"

## Ciclo completo: entrenar + test + lint
all: train test lint

help:
	@echo "Targets disponibles:"
	@grep -E '^## ' Makefile | sed 's/## /  /'
	@echo ""
	@echo "Uso: make train | make test | make train-eval | make all"
