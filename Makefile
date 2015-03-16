test:
	py.test
build:
	dpkg-buildpackage -us -uc
