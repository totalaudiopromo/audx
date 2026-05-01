.PHONY: test lint format build publish

test:
	pytest -q

lint:
	flake8 src/
	mypy src/

format:
	black src/ tests/
	isort src/ tests/

build:
	python -m build

publish-npm:
	npm publish

publish-py:
	twine upload dist/*
