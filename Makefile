.PHONY: run install test lint

run:
	uvicorn backend.app.main:app --reload --port 8000

install:
	pip install -r backend/requirements.txt

test:
	pytest -q

lint:
	ruff check backend