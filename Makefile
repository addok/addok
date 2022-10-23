test:
	py.test
testcoverage:
	py.test --cov=addok/
testall:
	py.test --quiet
	cd ../addok-france && py.test --quiet
	cd ../addok-fr && py.test --quiet
	cd ../addok-csv && py.test --quiet
	cd ../addok-sqlite-store && py.test --quiet
clean:
	rm -rf dist/* build/*
dist:
	python setup.py sdist bdist_wheel
upload:
	twine upload dist/*
