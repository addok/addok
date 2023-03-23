develop:
	pip install -e .
	pip install -r requirements-dev.txt
test:
	py.test
testcoverage:
	py.test --cov-report lcov --cov=addok/
testall:
	py.test --quiet
	cd ../addok-france && py.test --quiet
	cd ../addok-fr && py.test --quiet
	cd ../addok-csv && py.test --quiet
	cd ../addok-sqlite-store && py.test --quiet
clean:
	rm -rf dist/ build/
dist: test
	python setup.py sdist bdist_wheel
upload:
	twine upload dist/*
