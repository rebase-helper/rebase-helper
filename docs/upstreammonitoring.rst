How to use the rebase-helper for upstream monitoring systems
========================================================

The page describes the integration of the rebase-helper into upstream monitoring systems.

#### Install a rebase-helper package
- either as an RPM package::

  `dnf install rebase-helper`

- from GitHub::

  `git clone https://github.com/phracek/rebase-helper`

Nowadays only koji build systems are used as a support for upstream monitoring systems.


#### Patch the new sources and run a koji scratch build
###### Python API usage

   from rebasehelper.application import Application
  ~~~~
   cli = CLI(['--non-interactive', '--builds-nowait', '--buildtool', 'fedpkg', 'upstream_version'])
   rh = Application(cli)
   rh.set_upstream_monitoring() # Switches the rebase-helper to an upstream release monitoring mode.
   rh.run()
   rh.get_rebasehelper_data() # Gets all the information about the results
~~~~~~
###### Bash usage
`rebase-helper --non-interactive --builds-nowait --buildtool fedpkg upstream_version`

#### Download logs and RPMs for comparing with checkers
###### Python API usage
~~~~
  cli = CLI(['--non-interactive', '--builds-nowait', '--buildtool', 'fedpkg', '--build-tasks', 'old_id,new-id'])
  rh.run() # Downloads RPMs, logs and runs checkers and provides logs.
  rh.get_rebasehelper_data() # Gets all the information about the results
~~~~
###### Bash usage

   `rebase-helper --non-interactive --builds-nowait --buildtool fedpkg --build-tasks old_id,new-id`

