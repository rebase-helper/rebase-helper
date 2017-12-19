Rebasing in container
=====================

:program:`rebase-helper` can be run in Docker container. The package to be rebased
has to be specified in :envvar:`PACKAGE` environment variable. Alternatively,
you can set :envvar:`REPOSITORY` environment variable and point it to URL of any
dist-git repository. In both cases, you can reference a specific branch, tag or commit
by appending it to the package name or the repository URL:

:samp:`$ docker run -it -e PACKAGE=foo#branch=f26 rebasehelper/rebase-helper:latest --outputtool json`

Results of the rebase will be stored in an exported volume.
