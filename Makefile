SHELL := /bin/bash
VENV := .venv
PYTHON := $(VENV)/bin/python3
SCRIPTS_DIR := skills/epistemic-debt/scripts

.PHONY: venv lint test test-unit test-integration check install-hooks clean

# Rebuilt whenever requirements-dev.txt changes; otherwise `make venv` is a
# no-op on repeat runs (this file's mtime is the up-to-date marker).
$(VENV)/bin/activate: requirements-dev.txt
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements-dev.txt
	touch $(VENV)/bin/activate

venv: $(VENV)/bin/activate

lint: venv
	$(PYTHON) -m ruff check $(SCRIPTS_DIR)

test-unit: venv
	$(PYTHON) -m unittest discover -s $(SCRIPTS_DIR) -p "test_*.py"

test: test-unit

# The behavioral eval suite (evals/) needs `claude plugin eval`, gated
# behind early access — see evals/README.md. Not part of `check`/pre-push
# since it can't run in every environment yet.
test-integration:
	claude plugin eval . --scaffold --allow-tools Bash Write

validate-manifests: venv
	$(PYTHON) scripts/check_manifests.py

# Everything a push should be blocked on. Kept deliberately narrow (no
# test-integration) so the pre-push hook only requires things every
# contributor's machine can run.
check: lint test-unit validate-manifests

install-hooks:
	mkdir -p .git/hooks
	cp scripts/git-hooks/pre-push .git/hooks/pre-push
	chmod +x .git/hooks/pre-push
	@echo "Installed pre-push hook -> runs 'make check' before every push."

clean:
	rm -rf $(VENV) .ruff_cache
