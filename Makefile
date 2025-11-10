develop:
	pip install -e ".[dev]"
test:
	python -m pytest
testcoverage:
	python -m pytest --cov-report lcov --cov=addok/
testall:
	python -m pytest --quiet
	cd ../addok-france && python -m pytest --quiet
	cd ../addok-fr && python -m pytest --quiet
	cd ../addok-csv && python -m pytest --quiet
	cd ../addok-sqlite-store && python -m pytest --quiet
clean:
	rm -rf dist/ build/
dist: clean test
	python -m build
upload: dist
	@if [ -z "$$(ls dist/*.whl dist/*.tar.gz 2>/dev/null)" ]; then \
		echo "Error: No distribution files found. Run 'make dist' first."; \
		exit 1; \
	fi
	twine upload dist/*
