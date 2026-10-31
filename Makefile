.PHONY: help install install-lite run seed produce test smoke docker docker-down clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

install: ## Create venv and install full requirements
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

install-lite: ## Install the minimal set (no torch/faiss/opencv)
	pip install -r requirements-lite.txt

run: ## Start the development server
	python run_server.py

seed: ## Seed demo story, products and vector index
	python scripts/seed_demo.py

produce: ## Build cover + interior + metadata + zip into output/
	python scripts/produce_demo.py

test: ## Run pytest
	python -m pytest

smoke: ## End-to-end checks through the Flask test client
	python scripts/smoke_test.py

docker: ## Build and start the full stack
	docker compose up --build

docker-down: ## Stop the stack
	docker compose down

clean: ## Remove generated artifacts
	rm -rf output/*.pdf output/*.json output/*_final_export output/*.zip .pytest_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
