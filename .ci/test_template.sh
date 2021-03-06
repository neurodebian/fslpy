#!/usr/bin/env bash

set -e

# If running on a fork repository, we merge in the
# upstream/master branch. This is done so that merge
# requests from fork to the parent repository will
# have unit tests run on the merged code, something
# which gitlab CE does not currently do for us.
if [[ "$CI_PROJECT_PATH" != "$UPSTREAM_PROJECT" ]]; then
  git fetch upstream;
  git merge --no-commit --no-ff upstream/master;
fi;

source /test.venv/bin/activate

# All other deps can be installed as normal.
# We install test dependenciesd through pip,
# because if we let setuptools do it, it
# will build/install everything from source,
# rather than using wheels.
pip install -r requirements.txt
pip install sphinx sphinx-rtd-theme
pip install pytest pytest-cov pytest-html pytest-runner mock coverage

# style stage
if [ "$TEST_STYLE"x != "x" ]; then pip install pylint flake8; fi;
if [ "$TEST_STYLE"x != "x" ]; then flake8                           fsl || true; fi;
if [ "$TEST_STYLE"x != "x" ]; then pylint --output-format=colorized fsl || true; fi;
if [ "$TEST_STYLE"x != "x" ]; then exit 0; fi

# We need the FSL atlases for the atlas
# tests, and need $FSLDIR to be defined
export FSLDIR=/fsl/
mkdir -p $FSLDIR/data/
rsync -rv "fsldownload:data/atlases/" "$FSLDIR/data/atlases/"

# Finally, run the damned tests.

# We run some tests under xvfb-run
# because they invoke wx. Sleep in
# between, otherwise xvfb gets upset.
xvfb-run python setup.py test --addopts="$TEST_OPTS tests/test_idle.py"
sleep 5
xvfb-run python setup.py test --addopts="$TEST_OPTS tests/test_platform.py"

# We run the immv/imcpy tests as the nobody
# user because some tests expect permission
# denied errors when looking at files, and
# root never gets denied. Make everything in
# this directory writable by anybody (which,
# unintuitively, includes nobody)
chmod -R a+w `pwd`
su -s /bin/bash -c 'source /test.venv/bin/activate && python setup.py test --addopts="$TEST_OPTS tests/test_immv_imcp.py"' nobody

# All other tests can be run as normal
python setup.py test --addopts="$TEST_OPTS --ignore=tests/test_idle.py --ignore=tests/test_platform.py --ignore=tests/test_immv_imcp.py"
python -m coverage report
