Writing plugins
===============

Starting with version 0.10.0, :program:`rebase-helper` is extensible through plugins.

You can implement your own build tool, checker, output tool, SPEC hook, build log hook or versioneer.
All you have to do is to derive your plugin from corresponding base class, implement
all necessary methods and register it using one of the following entry points:

================= ===================================== ==============================================================
Plugin type       Entry point                           Base class
================= ===================================== ==============================================================
build tool        :samp:`rebasehelper.build_tools`      :samp:`rebasehelper.plugins.build_tools.rpm.BuildToolBase`
SRPM build tool   :samp:`rebasehelper.srpm_build_tools` :samp:`rebasehelper.plugins.build_tools.srpm.SRPMBuildToolBase`
checker           :samp:`rebasehelper.checkers`         :samp:`rebasehelper.plugins.checkers.BaseChecker`
output tool       :samp:`rebasehelper.output_tools`     :samp:`rebasehelper.plugins.output_tools.BaseOutputTool`
SPEC hook         :samp:`rebasehelper.spec_hooks`       :samp:`rebasehelper.plugins.spec_hooks.BaseSpecHook`
build log hook    :samp:`rebasehelper.build_log_hooks`  :samp:`rebasehelper.plugins.build_log_hooks.BaseBuildLogHook`
versioneer        :samp:`rebasehelper.versioneers`      :samp:`rebasehelper.plugins.versioneers.BaseVersioneer`
================= ===================================== ==============================================================


Example
-------

.. code-block:: python
   :caption: my_spec_hook/__init__.py

   from rebasehelper.plugins.spec_hooks import BaseSpecHook


   class MySpecHook(BaseSpecHook):

       NAME = 'MySpecHook'

       @classmethod
       def get_name(cls):
           return cls.NAME

       @classmethod
       def run(cls, spec_file, rebase_spec_file):
           """
           This method is called after original SPEC file is processed

           :param spec_file: SpecFile object representing original SPEC file
           :param rebase_spec_file: SpecFile object representing rebased SPEC file
           """
           rebase_spec_file.spec_content.section('%package').insert(0, '# processed by {}\n'.format(cls.NAME))
           rebase_spec_file.save()

.. code-block:: python
   :caption: setup.py

   from setuptools import setup


   setup(
       name='MySpecHook',
       version='0.1',
       description='Custom SPEC hook for rebase-helper',
       author='John Doe',
       install_requires=['rebasehelper>=0.10.0'],
       packages=['my_spec_hook'],
       entry_points={
           'rebasehelper.spec_hooks': ['my_spec_hook = my_spec_hook:MySpecHook']
       }
   )
