# -*- coding: utf-8 -*-
"""Manage App dependencies."""
import sys
import shutil
from hashlib import sha1
from pathlib import Path
from subprocess import run, PIPE, CalledProcessError


class AppEnvironment:
    """Manage the environment for AiiDA lab app dependencies.

    Arguments:

        app_dir:
            Absolute path to the AiiDA lab app.
    """

    def __init__(self, app_dir):
        self.app_dir = Path(app_dir).resolve()

    @property
    def prefix(self):
        return self.app_dir.joinpath('.aiidalab-dependencies')

    def _install_dependencies(self):
        """Install the app's dependencies into the local prefix."""
        # Install as editable package if 'setup.py' is present.
        if self.app_dir.joinpath('setup.py').is_file():
            run([sys.executable, '-m', 'pip', 'install', f'--target={self.prefix}', '.'],
                capture_output=True,
                check=True,
                cwd=self.app_dir)
            return sha1(self.app_dir.joinpath('setup.py').read_bytes()).hexdigest()

        # Otherwise, install from 'requirements.txt' if present.
        if self.app_dir.joinpath('requirements.txt').is_file():
            run([sys.executable, '-m', 'pip', 'install', f'--target={self.prefix}', '-r', 'requirements.txt'],
                capture_output=True,
                check=True,
                cwd=self.app_dir)
            return sha1(self.app_dir.joinpath('requirements.txt').read_bytes()).hexdigest()

        return None

    def _run_post_install_script(self):
        """Run the post_install script.

        Typically used to execute additional commands after the app dependency installation.
        """
        assert self.app_dir.joinpath('post_install').is_file()
        return run(['./post_install'], check=True, cwd=self.app_dir, stderr=PIPE)

    def install(self, clear=True):  # pylint: disable=too-many-branches
        """Install the app's dependencies and link them into the app directory."""
        if clear:
            self.uninstall()

        try:
            # Try to install dependencies
            try:
                yield "Install app dependencies..."
                checksum = self._install_dependencies()
            except CalledProcessError as error:
                raise RuntimeError(f"Failed to install app dependencies: {error.stderr.decode()}.")
            else:
                if checksum:

                    # Link all the dependencies into the app directory
                    record = self.prefix.joinpath('RECORD')
                    with record.open('w') as file:
                        for child in self.prefix.iterdir():
                            if child.samefile(record):
                                continue  # do not link the record file

                            dst = self.app_dir / child.relative_to(self.prefix)
                            try:
                                dst.symlink_to(child.relative_to(dst.parent))
                            except FileExistsError:
                                if not dst.samefile(child):
                                    raise RuntimeError(f"Unable to install '{child}', the path already exists.")
                            else:
                                file.write(f'{dst.relative_to(self.app_dir)}\n')

                    # Write the checksum file
                    self.prefix.joinpath('CHECKSUM').write_text(checksum)

        except Exception:
            self.uninstall()  # rollback
            raise
        else:
            # ... then run the post_install script (if present) ...
            if Path(self.app_dir).joinpath('post_install').is_file():
                try:
                    yield "Run post_install script..."
                    self._run_post_install_script()
                except CalledProcessError as error:
                    raise RuntimeError(f"Failed to execute post_install script.\n{error.stderr.decode()}")

            yield "Done."

    def uninstall(self):
        """Remove all installed dependencies from the app directory."""
        try:
            paths = [self.app_dir.joinpath(line) for line in self.prefix.joinpath('RECORD').read_text().splitlines()]
        except FileNotFoundError:
            pass
        else:
            for path in paths:
                try:
                    path.unlink()
                except FileNotFoundError:
                    continue
        finally:
            try:
                shutil.rmtree(self.prefix)
            except FileNotFoundError:
                pass

    def _has_dependencies(self):
        """Return True if the app has dependencies."""
        setup_py = Path(self.app_dir).joinpath('setup.py')
        requirements_txt = Path(self.app_dir).joinpath('requirements.txt')
        return setup_py.is_file() or requirements_txt.is_file()

    def _app_dependencies_checksum(self):
        """Return checksum of the app's dependencies specification."""
        setup_py = self.app_dir.joinpath('setup.py')
        requirements_txt = self.app_dir.joinpath('requirements.txt')

        if setup_py.is_file():
            return sha1(setup_py.read_bytes()).hexdigest()
        if requirements_txt.is_file():
            return sha1(requirements_txt.read_bytes()).hexdigest()
        return None

    def _installed_app_dependencies_checksum(self):
        """Return the version of dependencies that are currently installed."""
        try:
            return self.prefix.joinpath('CHECKSUM').read_text()
        except FileNotFoundError:
            return None

    def message(self):
        """Return a message describing an issue with the app's environment.

        Returns an empty string if there is no issue.
        """
        if self._has_dependencies():
            if self.prefix.is_dir():
                if self._installed_app_dependencies_checksum() != self._app_dependencies_checksum():
                    return "The dependencies installed into the dedicated app environment are not current."
            else:
                return "Dedicated app environment is not installed."
        return ''
