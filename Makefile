PYTHON = python


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
	@echo " completion              generate bash completion script"
	@echo " test                    run test suite"
	@echo " test-docker             run test suite inside Docker containers for several Fedora releases"


clean:
	@$(PYTHON) setup.py clean
	rm -f MANIFEST
	rm -rf build/html
	rm -rf build/man
	find . -\( -name "*.pyc" -o -name '*.pyo' -o -name "*~" -\) -delete


install:
	@$(PYTHON) setup.py install


build:
	@$(PYTHON) setup.py build


log:
	@(LC_ALL=C date +"* %a %b %e %Y `git config --get user.name` <`git config --get user.email`> - VERSION"; git log --pretty="format:- %s (%an)" | cat) | less


source: clean
	@$(PYTHON) setup.py sdist


html: build
	make -f Makefile.docs html


man: build
	make -f Makefile.docs man


completion: build
	$(PYTHON) -m rebasehelper.completion rebase-helper.bash.in build/rebase-helper.bash


test:
	tox


test-docker: clean
	make -f Makefile.docker test
