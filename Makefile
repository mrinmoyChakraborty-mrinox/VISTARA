.PHONY: run install test smoke

run:
	uvicorn backend.app.main:app --reload --port 8000

install:
	pip install -r backend/requirements.txt

test:
	pytest -q

# Stage 1+ (placeholder target; script lands in Stage 1)
smoke:
	python scripts/vlm_smoke_test.py
