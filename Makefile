.DEFAULT_GOAL := help

.PHONY: help format lint check test cov test-fast docs docs-serve docs-deploy clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

format: ## Format code with ruff
	hatch run format src tests

lint: ## Run ruff linter with auto-fix
	hatch run lint

check: ## Run all checks (ruff + mypy)
	hatch run check

test: ## Run tests
	hatch run test

cov: ## Run tests with coverage
	hatch run cov

test-fast: ## Run tests in parallel
	hatch run test-fast

docs: ## Build documentation
	hatch run docs:build

docs-serve: ## Serve documentation locally
	hatch run docs:serve

docs-deploy: ## Deploy documentation to GitHub Pages
	hatch run docs:deploy

clean: ## Clean build artifacts
	rm -rf dist/ build/ site/ .mypy_cache/ .pytest_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

