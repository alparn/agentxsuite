.PHONY: lint typecheck test run migrate install

install:
	pip install -r requirements/base.txt
	pip install -r requirements/dev.txt
	pip install -r requirements/test.txt

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .

typecheck:
	mypy apps libs

test:
	pytest apps/ libs/ -v

test-cov:
	pytest apps/ libs/ --cov=apps --cov=libs --cov-report=term-missing

migrate:
	python manage.py makemigrations
	python manage.py migrate

run:
	python manage.py runserver

run-mcp-fabric:
	uvicorn mcp_fabric.main:app --reload --port 8090 --host 0.0.0.0

