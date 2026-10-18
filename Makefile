# BugSight QA - Makefile
# Recipes must be indented with TABS.

ifeq ($(OS),Windows_NT)
VENV_BIN := .venv/Scripts
else
VENV_BIN := .venv/bin
endif

PYTHON := $(VENV_BIN)/python
PIP := $(VENV_BIN)/pip
RUFF := $(VENV_BIN)/ruff

.DEFAULT_GOAL := help
.PHONY: help install data train evaluate serve frontend test lint format check-i18n ci docker docker-down clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Create venv and install dependencies
	python -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PIP) install -r requirements.txt
	cd frontend && npm ci

data:  ## Generate the six-class synthetic dataset (1500 images) in data/processed_v2
	$(PYTHON) scripts/generate_dataset.py --n-images 1500 --output data/processed_v2

train:  ## Train the YOLOv8 model
	$(PYTHON) scripts/train.py --config configs/train.yaml

evaluate:  ## Per-class evaluation of the newest weights (test split)
	$(PYTHON) scripts/evaluate.py

serve:  ## Start the Flask API (development)
	$(PYTHON) scripts/serve.py --debug

frontend:  ## Start the React dev server
	cd frontend && npm run dev

test:  ## Run all Python tests
	$(PYTHON) -m pytest tests/ -v

lint:  ## Lint and format-check Python code
	$(RUFF) check src tests scripts
	$(RUFF) format --check src tests scripts

format:  ## Auto-fix lint issues and format Python code
	$(RUFF) check --fix src tests scripts
	$(RUFF) format src tests scripts

check-i18n:  ## Check that EN and FR translation files have the same keys
	cd frontend && npm run check:i18n

ci: lint check-i18n test  ## Run the same checks as CI

docker:  ## Build and start the full stack with Docker (needs JWT_SECRET in .env)
	docker compose up --build

docker-down:  ## Stop the Docker stack
	docker compose down

clean:  ## Remove generated artifacts
	rm -rf data/processed runs .pytest_cache .coverage htmlcov
	find . -path ./.venv -prune -o -path ./frontend/node_modules -prune -o -type d -name __pycache__ -exec rm -rf {} +
