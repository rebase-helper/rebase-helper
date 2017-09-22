import json
import os
import re
import shutil
import sys
import tempfile
import traceback

import git
import rpm
import six
import unidiff

from rebasehelper.application import Application
from rebasehelper.cli import CLI, Config
from rebasehelper.constants import RESULTS_DIR
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.logger import LoggerHelper
from rebasehelper.helpers.koji_helper import koji, KojiHelper


CLONE_URL = 'https://src.fedoraproject.org/rpms'
SESSION_FILENAME = 'batch.json'
REBASE_PATCH_FILENAME = 'rebase.patch'
TRACEBACK_FILENAME = 'traceback.txt'
DEFAULT_PACKAGE_COUNT = 100


class Batch(object):
    def __init__(self, workdir):
        self.workdir = workdir
        self.session = {}

    @classmethod
    def _print(cls, message):
        cnt = (78 - len(message)) // 2
        print('{0} {1} {0}'.format('=' * cnt, message))

    def _load_session(self):
        self.session = {}
        fn = os.path.join(self.workdir, SESSION_FILENAME)
        if os.path.isfile(fn):
            with open(fn) as f:
                self.session = json.load(f)

    def _save_session(self):
        fn = os.path.join(self.workdir, SESSION_FILENAME)
        with open(fn, 'w') as f:
            json.dump(self.session, f, sort_keys=True, indent=4, separators=(',', ': '))

    @classmethod
    def _get_suitable_packages(cls, limit):
        if not KojiHelper.functional:
            return []
        session = KojiHelper.create_session()
        builds = session.listBuilds(state=koji.BUILD_STATES['COMPLETE'], queryOpts=dict(order='-build_id', limit=limit))
        result = []
        for build in builds:
            if build['completion_ts'] - build['creation_ts'] > 30 * 60:
                continue
            try:
                clog = session.getChangelogEntries(buildID=build['build_id'])
            except TypeError:
                continue
            # Fedora Release Engineering <releng@fedoraproject.org> - 0.74-26
            author_re = re.compile(r'^.+ - (?P<E>\d+:)?(?P<V>.+)-(?P<R>\d+)$')
            rebased = False
            epoch_changed = False
            for entry in clog:
                m = author_re.match(entry.get('author'))
                if not m:
                    continue
                d = m.groupdict()
                if d['V'] != build['version']:
                    rebased = True
                    epoch_changed = d['E'] != build['epoch']
                    break
            if not rebased or epoch_changed:
                continue
            result.append(build['package_name'])
        return result

    def _clone_dist_git(self, package):
        url = '{0}/{1}'.format(CLONE_URL, package)
        workdir = os.path.join(self.workdir, package)
        if os.path.isdir(workdir):
            shutil.rmtree(workdir)
        try:
            repo = git.Repo.clone_from(url, workdir)
        except git.exc.GitCommandError:
            return None, None
        return repo

    def _find_latest_rebase(self, package, repo):
        def get_version(stream):
            with tempfile.NamedTemporaryFile() as f:
                f.write(stream.read())
                f.flush()
                try:
                    spec = rpm.spec(f.name)
                except ValueError:
                    return None, None
                else:
                    return spec.sourceHeader[rpm.RPMTAG_EPOCHNUM], spec.sourceHeader[rpm.RPMTAG_VERSION].decode()
        workdir = os.path.join(self.workdir, package)
        spec = [f for f in os.listdir(workdir) if os.path.splitext(f)[1] == '.spec']
        if not spec:
            return None, None, None
        for commit in repo.iter_commits(paths=spec[0]):
            if not commit.parents:
                continue
            blob = [b for b in commit.parents[0].tree.blobs if b.name == spec[0]]
            if not blob:
                continue
            old_epoch, old_version = get_version(blob[0].data_stream)
            blob = [b for b in commit.tree.blobs if b.name == spec[0]]
            if not blob:
                continue
            new_epoch, new_version = get_version(blob[0].data_stream)
            if old_epoch != new_epoch:
                continue
            if old_version == new_version:
                continue
            diff = repo.git.diff(commit.parents[0], commit, stdout_as_string=False)
            repo.git.checkout(commit.parents[0], force=True)
            return old_version, new_version, diff
        return None, None, None

    def _rebase(self, package, version):
        os.chdir(os.path.join(self.workdir, package))
        os.environ['LANG'] = 'en_US'
        config = Config(None)
        cli = CLI([
            '--color', 'never',
            '--pkgcomparetool', 'licensecheck,rpmdiff,pkgdiff,abipkgdiff,sonamecheck',
            '--outputtool', 'json',
            '--non-interactive',
            '--favor-on-conflict', 'upstream',
            '--disable-inapplicable-patches',
            '--get-old-build-from-koji',
            '--update-sources',
            '--skip-upload',
            '--force-build-log-hooks',
            version
        ])
        config.merge(cli)
        execution_dir, results_dir = Application.setup(config)
        app = Application(config, self.workdir, execution_dir, results_dir)
        app.run()

    def _analyze(self, package):
        def analyze_srpm_build_log(log):
            error_re = re.compile(r'^error: (?P<error>.+)$')
            with open(log) as f:
                for line in f.readlines():
                    match = error_re.match(line)
                    if match:
                        return dict(srpm_build_error=match.groupdict()['error'])
            return {}
        def analyze_root_log(log):
            error_re = re.compile(r'^.*(BUILDSTDERR:\s+)?Error: (?P<error>.+)$')
            with open(log) as f:
                for line in f.readlines():
                    match = error_re.match(line)
                    if match:
                        return dict(build_env_error=match.groupdict()['error'])
            return {}
        def analyze_build_log(log):
            error_re = re.compile(r'^(BUILDSTDERR:\s+)?error: Bad exit status from .+ \((?P<section>%\w+)\)$')
            with open(log) as f:
                for line in f.readlines():
                    match = error_re.match(line)
                    if match:
                        return dict(build_failure_section=match.groupdict()['section'])
            return {}
        workdir = os.path.join(self.workdir, package, RESULTS_DIR)
        report_file = os.path.join(workdir, 'report.json')
        if not os.path.isfile(report_file):
            return {}
        with open(report_file) as f:
            report = json.load(f)
        result = {}
        try:
            result['result'] = list(report['result']).pop()
            for version in ['old', 'new']:
                if 'source_package_build_error' in report['builds'][version]:
                    result['build_failure_type'] = 'srpm'
                    result['build_failure_version'] = version
                    for log in report['builds'][version]['logs']:
                        if 'build.log' in log and 'SRPM' in log:
                            result.update(analyze_srpm_build_log(log))
                elif 'binary_package_build_error' in report['builds'][version]:
                    result['build_failure_type'] = 'rpm'
                    result['build_failure_version'] = version
                    for log in report['builds'][version]['logs']:
                        if 'root.log' in log:
                            result.update(analyze_root_log(log))
                        elif 'build.log' in log and not 'SRPM' in log:
                            result.update(analyze_build_log(log))
        except KeyError:
            pass
        return result

    def _compare_rebase(self, package, diff):
        def get_info(patch, kind):
            return set(['{0} +{1} -{2}'.format(f.path, f.added, f.removed) for f
                        in getattr(patch, '{0}_files'.format(kind))])
        workdir = os.path.join(self.workdir, package, RESULTS_DIR)
        report_file = os.path.join(workdir, 'report.json')
        if not os.path.isfile(report_file):
            return {}
        with open(report_file) as f:
            report = json.load(f)
        try:
            changes_patch = report['changes_patch']['changes_patch']
        except KeyError:
            return {}
        patch1 = unidiff.PatchSet.from_string(diff, encoding='UTF-8')
        patch2 = unidiff.PatchSet.from_filename(changes_patch, encoding='UTF-8')
        return dict(diffs=dict(
            added=list(get_info(patch1, 'added').symmetric_difference(get_info(patch2, 'added'))),
            modified=list(get_info(patch1, 'modified').symmetric_difference(get_info(patch2, 'modified'))),
            removed=list(get_info(patch1, 'removed').symmetric_difference(get_info(patch2, 'removed')))
        ))

    def run(self):
        self._load_session()
        if not self.session:
            if sys.stdin.isatty():
                count = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PACKAGE_COUNT
                self._print('Getting list of packages from Koji')
                packages = set()
                n = 2
                while len(packages) < count:
                    packages.update(self._get_suitable_packages(max(n * count, 10)))
                    n += 1
                self.session['_packages_'] = list(packages)[:count]
            else:
                self.session['_packages_'] = [pkg.strip() for pkg in sys.stdin.readlines()]
        for pkg in self.session['_packages_']:
            if pkg in self.session:
                self._print('Package "{0}" already rebased'.format(pkg))
                continue
            self._print('Rebasing package "{0}"'.format(pkg))
            repo = self._clone_dist_git(pkg)
            if not repo:
                self._print('ERROR: Error cloning dist-git!')
                continue
            old_version, new_version, diff = self._find_latest_rebase(pkg, repo)
            if not old_version:
                self._print('ERROR: Latest rebase not found!')
                shutil.rmtree(os.path.join(self.workdir, pkg))
                continue
            self.session[pkg] = dict(old_version=old_version, new_version=new_version)
            with open(os.path.join(self.workdir, pkg, REBASE_PATCH_FILENAME), 'wb') as f:
                f.write(diff)
                f.write(b'\n')
            try:
                self._rebase(pkg, new_version)
            except RebaseHelperError as e:
                self.session[pkg]['rh_error'] = e.msg if e.msg else six.text_type(e)
            except Exception as e:
                self.session[pkg]['exception'] = six.text_type(e)
                exc_type, exc_obj, exc_tb = sys.exc_info()
                with open(os.path.join(self.workdir, pkg, TRACEBACK_FILENAME), 'w') as f:
                    f.write('Traceback (most recent call last):\n')
                    f.write(''.join(traceback.format_tb(exc_tb)))
                    f.write('{0}: {1}\n'.format(exc_type, six.text_type(exc_obj)))
            self.session[pkg].update(self._analyze(pkg))
            self.session[pkg].update(self._compare_rebase(pkg, diff))
            self._save_session()


def main():
    LoggerHelper.create_stream_handlers()
    Batch(os.getcwd()).run()


if __name__ == '__main__':
    main()
