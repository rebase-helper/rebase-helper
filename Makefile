all: help


help:
	@echo "Usage: make <target>"
	@echo
	@echo "Available targets are:"
	@echo " help                    show this text"
	@echo " clean                   remove python bytecode and temp files"
	@echo " install                 install program on current system"
	@echo " build                   build program"
	@echo " log                     prepare changelog for spec file"
	@echo " source                  create source tarball"
	@echo " html                    create HTML documentation"
	@echo " man                     generate manual page"
	@echo " test                    run test suite"
	@echo " test-docker             run test suite inside Docker containers for several Fedora releases"


clean:
	@python setup.py clean
	rm -f MANIFEST
	rm -rf build/html
	rm -rf build/man
	find . -\( -name "*.pyc" -o -name '*.pyo' -o -name "*~" -\) -delete


install:
	@python setup.py install


build:
	@python setup.py build


log:
	@(LC_ALL=C date +"* %a %b %e %Y `git config --get user.name` <`git config --get user.email`> - VERSION"; git log --pretty="format:- %s (%an)" | cat) | less


source: clean
	@python setup.py sdist


html: build
	make -f Makefile.docs html


man: build
	make -f Makefile.docs man


test:
	tox --recreate


test-docker:
	make -f Makefile.docker test
