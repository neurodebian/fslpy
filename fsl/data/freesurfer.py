#!/usr/bin/env python
#
# freesurfer.py - The FreesurferMesh class.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides the :class:`FreesurferMesh` class, which can be
used for loading Freesurfer geometry and vertex data files.

The following functions are also available:

  .. autosummary::
     :nosignatures:

     relatedFiles
"""


import os.path as op
import            glob

import nibabel as nib

import fsl.utils.path as fslpath
import fsl.data.mesh  as fslmesh


ALLOWED_EXTENSIONS = ['.pial',
                      '.white',
                      '.sphere',
                      '.inflated',
                      '.orig',
                      '.mid']
"""File extensions which are interpreted as Freesurfer geometry files. """


EXTENSION_DESCRIPTIONS = [
    "Freesurfer surface",
    "Freesurfer surface",
    "Freesurfer surface",
    "Freesurfer surface",
    "Freesurfer surface",
    "Freesurfer surface"]
"""A description for each extension in :attr:`ALLOWED_EXTENSIONS`. """


class FreesurferMesh(fslmesh.Mesh):
    """The :class:`FreesurferMesh` class represents a triangle mesh
    loaded from a Freesurfer geometry file.
    """


    def __init__(self, filename, fixWinding=False, loadAll=False):
        """Load the given Freesurfer surface file using ``nibabel``.

        :arg infile:     A Freesurfer geometry file  (e.g. ``*.pial``).

        :arg fixWinding: Passed through to the :meth:`addVertices` method
                         for the first vertex set.

        :arg loadAll:    If ``True``, the ``infile`` directory is scanned
                         for other freesurfer surface files which are then
                         loaded as additional vertex sets.
        """

        vertices, indices, meta, comment = nib.freesurfer.read_geometry(
            filename,
            read_metadata=True,
            read_stamp=True)

        filename = op.abspath(filename)
        name     = fslpath.removeExt(op.basename(filename),
                                     ALLOWED_EXTENSIONS)

        fslmesh.Mesh.__init__(self,
                              indices,
                              name=name,
                              dataSource=filename)

        self.addVertices(vertices, filename, fixWinding=fixWinding)

        self.setMeta('comment', comment)
        for k, v in meta.items():
            self.setMeta(k, v)

        if loadAll:

            allFiles = relatedFiles(filename, ftypes=ALLOWED_EXTENSIONS)

            for f in allFiles:
                verts, idxs = nib.freesurfer.read_geometry(f)
                self.addVertices(verts, f, select=False)


    def loadVertexData(self, infile, key=None):
        """
        """
        pass


def loadFreesurferVertexFile(infile):
    pass


def relatedFiles(fname, ftypes=None):
    """Returns a list of all files which (look like they) are related to the
    given freesurfer file.
    """

    if ftypes is None:
        ftypes = ['.annot', '.label', '.curv', '.w']

    #
    # .annot files contain labels for each vertex, and RGB values for each
    #  label
    #    -> nib.freesurfer.read_annot
    #
    # .label files contain scalar labels associated with each vertex
    #    -> read_label
    #
    # .curv files contain vertex data
    #    -> nib.freesurfer.read_morph_data
    #
    # .w files contain vertex data (potentially for a subset of vertices)
    #    -> ?

    prefix  = op.splitext(fname)[0]
    related = []

    for ftype in ftypes:
        related += list(glob.glob('{}{}'.format(prefix, ftype)))

    return [r for r in related if r != fname]