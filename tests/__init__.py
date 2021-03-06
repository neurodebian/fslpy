#!/usr/bin/env python
#
# __init__.py - fslpy tests
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""Unit tests for ``fslpy``. """


import              os
import              sys
import              glob
import              shutil
import              tempfile
import              logging
import              contextlib
import itertools as it
import os.path   as op
import numpy     as np
import nibabel   as nib

from six import StringIO

import fsl.data.image as fslimage


logging.getLogger().setLevel(logging.WARNING)



@contextlib.contextmanager
def tempdir():
    """Returnsa context manager which creates and returns a temporary
    directory, and then deletes it on exit.
    """

    testdir = tempfile.mkdtemp()
    prevdir = os.getcwd()
    try:

        os.chdir(testdir)
        yield testdir

    finally:
        os.chdir(prevdir)
        shutil.rmtree(testdir)


class CaptureStdout(object):
    """Context manager which captures stdout and stderr. """

    def __init__(self):
        self.reset()

    def reset(self):
        self.__mock_stdout = StringIO('')
        self.__mock_stderr = StringIO('')

    def __enter__(self):
        self.__real_stdout = sys.stdout
        self.__real_stderr = sys.stderr

        sys.stdout = self.__mock_stdout
        sys.stderr = self.__mock_stderr


    def __exit__(self, *args, **kwargs):
        sys.stdout = self.__real_stdout
        sys.stderr = self.__real_stderr

        if args[0] is not None:
            print('Error')
            print('stdout:')
            print(self.stdout)
            print('stderr:')
            print(self.stderr)

        return False

    @property
    def stdout(self):
        self.__mock_stdout.seek(0)
        return self.__mock_stdout.read()

    @property
    def stderr(self):
        self.__mock_stderr.seek(0)
        return self.__mock_stderr.read()



def testdir(contents=None):
    """Returnsa context manager which creates, changes to, and returns a
    temporary directory, and then deletes it on exit.
    """

    if contents is not None:
        contents = [op.join(*c.split('/')) for c in contents]

    class ctx(object):

        def __init__(self, contents):
            self.contents = contents

        def __enter__(self):

            self.testdir = tempfile.mkdtemp()
            self.prevdir = os.getcwd()

            os.chdir(self.testdir)

            if self.contents is not None:
                contents = [op.join(self.testdir, c) for c in self.contents]
                make_dummy_files(contents)

            return self.testdir

        def __exit__(self, *a, **kwa):
            os.chdir(self.prevdir)
            shutil.rmtree(self.testdir)

    return ctx(contents)

def make_dummy_files(paths):
    """Creates dummy files for all of the given paths. """
    for p in paths:
        make_dummy_file(p)


def make_dummy_file(path, contents=None):
    """Makes a plain text file. Returns a hash of the file contents. """
    dirname = op.dirname(path)

    if not op.exists(dirname):
        os.makedirs(dirname)

    if contents is None:
        contents = '{}\n'.format(op.basename(path))
    with open(path, 'wt') as f:
        f.write(contents)

    return hash(contents)


def looks_like_image(path):
    """Returns True if the given path looks like a NIFTI/ANALYZE image.
    """
    return any((path.endswith('.nii'),
                path.endswith('.nii.gz'),
                path.endswith('.img'),
                path.endswith('.hdr'),
                path.endswith('.img.gz'),
                path.endswith('.hdr.gz')))


def make_dummy_image_file(path):
    """Makes some plain files with NIFTI/ANALYZE file extensions.
    """

    if   path.endswith('.nii'):    paths = [path]
    elif path.endswith('.nii.gz'): paths = [path]
    elif path.endswith('.img'):    paths = [path, path[:-4] + '.hdr']
    elif path.endswith('.hdr'):    paths = [path, path[:-4] + '.img']
    elif path.endswith('.img.gz'): paths = [path, path[:-7] + '.hdr.gz']
    elif path.endswith('.hdr.gz'): paths = [path, path[:-7] + '.img.gz']
    else: raise RuntimeError()

    for path in paths:
        make_dummy_file(path)


def cleardir(dir):
    """Deletes everything in the given directory, but not the directory
    itself.
    """
    for f in os.listdir(dir):
        f = op.join(dir, f)
        if   op.isfile(f): os.remove(f)
        elif op.isdir(f):  shutil.rmtree(f)


def random_voxels(shape, nvoxels=1):
    randVoxels = np.vstack(
        [np.random.randint(0, s, nvoxels) for s in shape[:3]]).T

    if nvoxels == 1:
        return randVoxels[0]
    else:
        return randVoxels


def make_random_image(filename, dims=(10, 10, 10), xform=None):
    """Creates a NIFTI1 image with random data, saves and
    returns it.
    """

    if xform is None:
        xform = np.eye(4)

    data = np.array(np.random.random(dims) * 100, dtype=np.float32)
    img  = nib.Nifti1Image(data, xform)

    nib.save(img, filename)

    return img

def make_mock_feat_analysis(featdir,
                            testdir,
                            shape4D,
                            xform=None,
                            indata=True,
                            voxEVs=True,
                            pes=True,
                            copes=True,
                            zstats=True,
                            residuals=True,
                            clustMasks=True):

    if xform is None:
        xform = np.eye(4)

    timepoints = shape4D[ 3]
    shape      = shape4D[:3]

    src     = featdir
    dest    = op.join(testdir, op.basename(featdir))
    featdir = dest

    shutil.copytree(src, dest)

    if indata:
        filtfunc = op.join(featdir, 'filtered_func_data.nii.gz')
        make_random_image(filtfunc, shape4D, xform)

    # and some dummy voxelwise EV files
    if voxEVs:
        voxFiles = list(it.chain(
            glob.glob(op.join(featdir, 'designVoxelwiseEV*nii.gz')),
            glob.glob(op.join(featdir, 'InputConfoundEV*nii.gz'))))

        for i, vf in enumerate(voxFiles):

            # Each voxel contains range(i, i + timepoints),
            # offset by the flattened voxel index
            data = np.meshgrid(*[range(s) for s in shape], indexing='ij')
            data = np.ravel_multi_index(data, shape)
            data = data.reshape(list(shape) + [1]).repeat(timepoints, axis=3)
            data[..., :] += range(i, i + timepoints)

            nib.save(nib.nifti1.Nifti1Image(data, xform), vf)

    otherFiles  = []
    otherShapes = []

    if pes:
        files = glob.glob(op.join(featdir, 'stats', 'pe*nii.gz'))
        otherFiles .extend(files)
        otherShapes.extend([shape] * len(files))

    if copes:
        files = glob.glob(op.join(featdir, 'stats', 'cope*nii.gz'))
        otherFiles .extend(files)
        otherShapes.extend([shape] * len(files))

    if zstats:
        files = glob.glob(op.join(featdir, 'stats', 'zstat*nii.gz'))
        otherFiles .extend(files)
        otherShapes.extend([shape] * len(files))

    if residuals:
        files = glob.glob(op.join(featdir, 'stats', 'res4d.nii.gz'))
        otherFiles .extend(files)
        otherShapes.extend([shape4D])

    if clustMasks:
        files = glob.glob(op.join(featdir, 'cluster_mask*nii.gz'))
        otherFiles .extend(files)
        otherShapes.extend([shape] * len(files))

    for f, s in zip(otherFiles, otherShapes):
        make_random_image(f, s, xform)

    return featdir



def make_random_mask(filename, shape, xform, premask=None):
    """Make a random binary mask image. """

    mask = np.zeros(shape, dtype=np.uint8)

    numones = np.random.randint(1, np.prod(shape) / 100)
    xc      = np.random.randint(0, shape[0], numones)
    yc      = np.random.randint(0, shape[1], numones)
    zc      = np.random.randint(0, shape[2], numones)

    mask[xc, yc, zc] = 1

    if premask is not None:
        mask[premask == 0] = 0

    img = fslimage.Image(mask, xform=xform)
    img.save(filename)

    return img
