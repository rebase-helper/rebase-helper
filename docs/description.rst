.. program description

:program:`rebase-helper` is a tool which helps package maintainers
to rebase their packages to latest upstream versions.

It should be executed from a directory containing spec file, sources
and patches (usually cloned dist-git repository).

The new version is specified by :option:`SOURCES` argument, which can be
either version number or filename of the new source archive.
Starting with version 0.10.0, this argument can be omitted and the new version
determined automatically using one of available *versioneers*.
