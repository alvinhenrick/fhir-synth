.DEFAULT_GOAL := help

.PHONY: help format test cov docs clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

format: ## Auto-fix, format, lint, and type check
	hatch run format

test: ## Run tests
	hatch run test

cov: ## Run tests with coverage
	hatch run cov

docs: ## Serve documentation locally
	hatch run docs:serve

clean: ## Clean build artifacts
	rm -rf dist/ build/ site/ .mypy_cache/ .pytest_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

