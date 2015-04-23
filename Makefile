test:
	py.test
pypi:
	python setup.py sdist bdist_wheel upload
