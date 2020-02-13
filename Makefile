PYTHON = python3


.PHONY: help clean install build log source html man completion sample_config test test-docker test-podman


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
	@echo " test-docker             run containerized test suite using docker-compose for several Fedora releases"
	@echo " test-podman             run containerized test suite in a pod using podman for several Fedora releases"


clean:
	@$(PYTHON) setup.py clean
	rm -f MANIFEST
	rm -f build/rebase-helper.bash
	rm -rf build/html
	rm -rf build/man
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete


install:
	@$(PYTHON) setup.py install


build:
	@$(PYTHON) setup.py build


log:
	@(LC_ALL=C date +"* %a %b %e %Y `git config --get user.name` <`git config --get user.email`> - VERSION"; git log --pretty="format:- %s (%an)" | cat) | less


source: clean
	@$(PYTHON) setup.py sdist


html: build
	make -C docs clean html


man: build
	make -C docs clean man


completion: build
	$(PYTHON) -m rebasehelper.completion rebase-helper.bash.in build/rebase-helper.bash


sample_config: build
	$(PYTHON) -m rebasehelper.sample_config build/rebase-helper.cfg


test:
	tox


test-docker:
	make -C containers -f Makefile.docker test


test-podman:
	make -C containers -f Makefile.podman test
