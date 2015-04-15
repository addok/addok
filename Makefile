test:
	py.test
build:
	dpkg-buildpackage -us -uc
servedoc:
	mkdocs serve
