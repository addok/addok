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
dist: test
	python -m build
upload:
	twine upload dist/*
