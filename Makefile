.PHONY: install test test-v1.1 test-v1.2 lint typecheck schema clean

install:
	pip install -e ".[dev]"

test:
	pytest -q -m "not feature_flag"

test-v1.1:
	pytest -q -m "not feature_flag or feature_flag_v1_1"

test-v1.2:
	pytest -q -m "not feature_flag or feature_flag_v1_1 or feature_flag_v1_2"

lint:
	ruff check src tests

typecheck:
	mypy src

schema:
	python -m tableau2pbir.ir.schema > schemas/ir-v1.1.0.schema.json

clean:
	rm -rf .tableau2pbir-cache .pytest_cache .mypy_cache .ruff_cache dist build
