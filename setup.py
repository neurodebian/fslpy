#!/usr/bin/env python
#
# setup.py - setuptools configuration for installing the fslpy package.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#


from __future__ import print_function

import os.path as op
import            shutil

from setuptools import setup
from setuptools import find_packages
from setuptools import Command


# The directory in which this setup.py file is contained.
basedir = op.dirname(__file__)

# Dependencies are listed in requirements.txt
install_requires = open(op.join(basedir, 'requirements.txt'), 'rt').readlines()

# Development/test dependencies are listed in requirements-dev.txt
dev_requires = open(op.join(basedir, 'requirements-dev.txt'), 'rt').readlines()

packages = find_packages(
    exclude=('doc', 'tests', 'dist', 'build', 'fslpy.egg-info'))

# Figure out the current fslpy version, as defined in fsl/version.py. We
# don't want to import the fsl package,  as this may cause build problems.
# So we manually parse the contents of fsl/version.py to extract the
# version number.
version = {}
with open(op.join(basedir, "fsl", "version.py")) as f:
    for line in f:
        if line.startswith('__version__'):
            exec(line, version)
            break
version = version['__version__']

with open(op.join(basedir, 'README.rst'), 'rt') as f:
    readme = f.read()


class doc(Command):
    """Build the API documentation. """

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):

        docdir  = op.join(basedir, 'doc')
        destdir = op.join(docdir, 'html')

        if op.exists(destdir):
            shutil.rmtree(destdir)

        print('Building documentation [{}]'.format(destdir))

        import sphinx

        try:
            import unittest.mock as mock
        except:
            import mock

        mockobj       = mock.MagicMock()
        mockobj.__version__ = '2.2.0'
        mockedModules = open(op.join(docdir, 'mock_modules.txt')).readlines()
        mockedModules = [l.strip()   for l in mockedModules]
        mockedModules = {m : mockobj for m in mockedModules}

        patches = [mock.patch.dict('sys.modules', **mockedModules)]

        [p.start() for p in patches]
        sphinx.main(['sphinx-build', docdir, destdir])
        [p.stop() for p in patches]


setup(

    name='fslpy',
    version=version,
    description='FSL Python library',
    long_description=readme,
    url='https://git.fmrib.ox.ac.uk/fsl/fslpy',
    author='Paul McCarthy',
    author_email='pauldmccarthy@gmail.com',
    license='Apache License Version 2.0',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries :: Python Modules'],

    packages=packages,

    install_requires=install_requires,
    setup_requires=dev_requires,

    test_suite='tests',

    cmdclass={'doc' : doc},

    entry_points={
        'console_scripts' : [
            'immv   = fsl.scripts.immv:main',
            'imcp   = fsl.scripts.imcp:main',
            'imglob = fsl.scripts.imglob:main',
            'atlasq = fsl.scripts.atlasq:main',
        ]
    }
)
