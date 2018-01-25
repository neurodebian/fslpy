#!/usr/bin/env python
#
# freesurfer.py - The FreesurferMesh class.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides the :class:`FreesurferMesh` class, which can be
used for loading Freesurfer geometry and vertex data files.


The following types of files generated by Freesurfer are recognised by this
module:


 - Core geometry files, defining the cortical mesh. Each core geometry
   file has the same number of vertices and same triangle definitions.

 - Extra geometry files, defining the cortical mesh. Extra geometry
   files may have a different number of vertices and/or triangle
   definitions.

 - Vertex data files (a.k.a. ``'curv'`` files), containing a scalar value for
   every vertex in the mesh. This data may also be contained in
   ``mgz``/``mgh`` files.

 - Label files, containing indices of a sub-set of vertices in the
   mesh.

 - Annotation files, containing a label value, and an RGBA colour for a
   subset of vertices in the mesh.


The following functions are also available:

  .. autosummary::
     :nosignatures:

     loadVertexDataFile
     isCoreGeometryFile
     isGeometryFile
     isVertexDataFile
     isVertexLabelFile
     isVertexAnnotFile
     relatedGeometryFiles
     relatedVertexDataFiles
     findReferenceImage
"""


import os.path   as op
import itertools as it
import              glob
import              fnmatch
import              collections

import numpy              as np
import nibabel.freesurfer as nibfs

import fsl.utils.path    as fslpath
import fsl.utils.memoize as memoize
import fsl.data.image    as fslimage
import fsl.data.mghimage as fslmgh
import fsl.data.mesh     as fslmesh


CORE_GEOMETRY_FILES = ['?h.orig',
                       '?h.pial',
                       '?h.white',
                       '?h.inflated',
                       '?h.sphere']
"""File patterns for identifying the core Freesurfer geometry files. """


CORE_GEOMETRY_DESCRIPTIONS = [
    "Freesurfer surface (original)",
    "Freesurfer surface (pial)",
    "Freesurfer surface (white matter)",
    "Freesurfer surface (inflated)",
    "Freesurfer surface (sphere)"]
"""A description for each extension in :attr:`GEOMETRY_EXTENSIONS`. """


EXTRA_GEOMETRY_FILES = ['?h.orig.nofix',
                        '?h.smoothwm.nofix',
                        '?h.inflated.nofix',
                        '?h.qsphere.nofix',
                        '?h.sphere.nofix',
                        '?h.white.preaparc']
"""Other geometry files which may be present in Freesurfer output. """


VERTEX_DATA_FILES = ['?h.thickness',
                     '?h.curv',
                     '?h.area',
                     '?h.sulc']
"""File patterns which are interpreted as Freesurfer vertex data files,
containing a scalar value for every vertex in the mesh.
"""


VERTEX_MGH_FILES = ['?h.*.mgh',
                    '?h.*.mgz']
"""File patterns which are interpreted as MGH files containing a
scalar value for every vertex in the mesh.
"""


VERTEX_LABEL_FILES = ['?h.*.label']
"""File patterns which are interpreted as Freesurfer vertex label files,
containing a scalar value for a sub-set of vertices in the mesh.
"""


VERTEX_ANNOT_FILES = ['?h.*.annot']
"""File patterns which are interpreted as Freesurfer vertex annotation files,
containing a scalar value and an RGBA colour for a sub-set of vertices in the
mesh.
"""


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

        vertices, indices, meta, comment = nibfs.read_geometry(
            filename,
            read_metadata=True,
            read_stamp=True)

        filename = op.abspath(filename)
        name     = op.basename(filename)

        fslmesh.Mesh.__init__(self,
                              indices,
                              name=name,
                              dataSource=filename)

        self.addVertices(vertices, filename, fixWinding=fixWinding)

        self.__luts = collections.OrderedDict()

        self.setMeta('comment', comment)
        for k, v in meta.items():
            self.setMeta(k, v)

        if loadAll:

            allFiles = relatedGeometryFiles(filename)

            for f in allFiles:
                verts, idxs = nibfs.read_geometry(f)
                self.addVertices(verts, f, select=False)


    def loadVertices(self, infile, key=None, **kwargs):
        """Overrides :meth:`.Mesh.loadVertices`. If the given ``infile``
        looks like a Freesurfer file, it is loaded via
        ``nibabel.freesurfer.load_geometry``. Otherwise, it is passed to
        :meth:`.Mesh.loadVertices`.
        """

        if not isGeometryFile(infile):
            return fslmesh.Mesh.loadVertices(self, infile, key, **kwargs)

        infile = op.abspath(infile)
        if key is None:
            key = infile

        # TODO merge metadata
        vertices, indices, meta, comment = nibfs.read_geometry(
            infile,
            read_metadata=True,
            read_stamp=True)

        return self.addVertices(vertices, key, **kwargs)


    def loadVertexData(self, infile, key=None):
        """Overrides :meth:`.Mesh.loadVertexData`. If the given ``infile``
        looks like a Freesurfer file, it is loaded via the
        :func:`loadVertexDataFile` function. Otherwise, it is passed through
        to the base-class function.

        If the given ``infile`` is a vertex annotation file, it is assumed
        that the file contains a value for every vertex in the mesh.
        """

        isvdata  = isVertexDataFile( infile)
        isvmgh   = isVertexMGHFile(  infile)
        isvlabel = isVertexLabelFile(infile)
        isvannot = isVertexAnnotFile(infile)

        if not any((isvdata, isvmgh, isvlabel, isvannot)):
            return fslmesh.Mesh.loadVertexData(self, infile)

        infile    = op.abspath(infile)
        nvertices = self.nvertices

        if key is None:
            key = infile

        vdata = loadVertexDataFile(infile)

        if isvlabel:
            # Currently ignoring scalar
            # values stored in label files
            idxs           = np.asarray(vdata[0])
            expanded       = np.zeros(nvertices)
            expanded[idxs] = 1
            vdata          = expanded

        elif isvannot:
            vdata, lut, names = vdata

        vdata = self.addVertexData(key, vdata)

        if isvannot:
            self.__luts[key] = lut, names

        return vdata


    def getVertexDataColourTable(self, key):
        """If the given ``key`` refers to a Freesurfer ``.annot`` file,
        the corresponding RGBA lookup table and label names can be
        retrieved via this method.
        """

        return self.__luts[key]


def loadVertexDataFile(infile):
    """Loads the given Freesurfer vertex data, label, or annotation file.

    This function return different things depending on what ``infile`` is:

     - If ``infile`` is a vertex data file, a ``(nvertices,)`` array is
       returned, containing one value for each vertex in the mesh.

     - If ``infile`` is a ``mgh``/``mgz`` file, the image data is returned
       as-is, with dimensions of length 1 squeezed out (under the assumption
       that the image contains scalar vertex data).

     - If ``infile`` is a vertex label file, a tuple containing the following
       is returned:

       - a ``(n,)`` array, containing the indices of all vertices that are
         specified in the file.

       - a ``(n,)`` array, containing scalar value for each vertex

     - If ``infile`` is a vertex annotation file, a tuple containing the
       following is returned:

       - a ``(n,)`` array  containing the indices of all ``n`` vertices that
         are specified in the file.

       - a ``(l, 5)`` array containing the RGBA colour, and the label value,
         for every label that is specified in the file.

       - A list of length ``l``, containing the names of every label that is
         specified in the file.

    """

    if isVertexDataFile(infile):
        return nibfs.read_morph_data(infile)

    elif isVertexLabelFile(infile):
        return nibfs.read_label(infile, read_scalars=True)

    elif isVertexAnnotFile(infile):

        # nibabel 2.2.1 is broken w.r.t. .annot files.
        # raise ValueError('.annot files are not yet supported')

        labels, lut, names = nibfs.read_annot(infile, orig_ids=False)
        return labels, lut, names

    elif isVertexMGHFile(infile):
        return fslmgh.MGHImage(infile)[:].squeeze()

    else:
        raise ValueError('Unrecognised freesurfer '
                         'file type: {}'.format(infile))


@memoize.memoize
def isCoreGeometryFile(infile):
    """Returns ``True`` if ``infile`` looks like a core Freesurfer geometry
    file, ``False`` otherwise.
    """
    infile = op.basename(infile)
    return any([fnmatch.fnmatch(infile, gf) for gf in CORE_GEOMETRY_FILES])


@memoize.memoize
def isGeometryFile(infile):
    """Returns ``True`` if ``infile`` looks like a Freesurfer geometry
    file (core or otherwise), ``False`` otherwise.
    """
    infile = op.basename(infile)
    return any([fnmatch.fnmatch(infile, gf)
                for gf in CORE_GEOMETRY_FILES + EXTRA_GEOMETRY_FILES])


@memoize.memoize
def isVertexDataFile(infile):
    """Returns ``True`` if ``infile`` looks like a Freesurfer vertex
    data file, ``False`` otherwise.
    """
    infile = op.basename(infile)
    return any([fnmatch.fnmatch(infile, gf) for gf in VERTEX_DATA_FILES])


@memoize.memoize
def isVertexMGHFile(infile):
    """Returns ``True`` if ``infile`` looks like a Freesurfer MGH file
    containing vertex data, ``False`` otherwise.
    """
    infile = op.basename(infile)
    return any([fnmatch.fnmatch(infile, gf) for gf in VERTEX_MGH_FILES])


@memoize.memoize
def isVertexLabelFile(infile):
    """Returns ``True`` if ``infile`` looks like a Freesurfer vertex
    label file, ``False`` otherwise.
    """
    infile = op.basename(infile)
    return any([fnmatch.fnmatch(infile, gf) for gf in VERTEX_LABEL_FILES])


@memoize.memoize
def isVertexAnnotFile(infile):
    """Returns ``True`` if ``infile`` looks like a Freesurfer vertex
    annotation file, ``False`` otherwise.
    """
    infile = op.basename(infile)
    return any([fnmatch.fnmatch(infile, gf) for gf in VERTEX_ANNOT_FILES])


def relatedGeometryFiles(fname):
    """Returns a list of all files which (look like they) are freesurfer
    geometry files which correspond to the given geometry file.
    """

    if not isCoreGeometryFile(fname):
        return []

    dirname, fname = op.split(op.abspath(fname))
    hemi           = fname[0]

    fpats          = [hemi + p[1:] for p in CORE_GEOMETRY_FILES]

    related        = [glob.glob(op.join(dirname, p)) for p in fpats]
    related        = list(it.chain(*related))

    return [r for r in related if op.basename(r) != fname]


def relatedVertexDataFiles(fname):
    """Returns a list of all files which (look like they) are vertex data,
    label, or annotation files related to the given freesurfer geometry file.
    """

    if not isCoreGeometryFile(fname):
        return []

    fname   = op.abspath(fname)
    dirname = op.dirname(fname)
    hemi    = op.basename(fname)[0]

    fpats   = (VERTEX_DATA_FILES  +
               VERTEX_LABEL_FILES +
               VERTEX_ANNOT_FILES +
               VERTEX_MGH_FILES)
    fpats   = [hemi + p[1:] if p.startswith('?h') else p for p in fpats]

    basedir    = op.dirname(dirname)
    searchDirs = set([dirname,
                      op.join(basedir, 'surf'),
                      op.join(basedir, 'stats'),
                      op.join(basedir, 'label')])

    searchPats = it.product(searchDirs, fpats)

    related = []

    for sdir, spat in searchPats:
        related.extend(glob.glob(op.join(sdir, spat)))

    return related


def findReferenceImage(fname):
    """Attempts to locate the volumetric reference image for (what is
    assumed to be) the given Freesurfer geometry file.
    """

    basedir = op.dirname(op.dirname(op.abspath(fname)))
    t1      = op.join(basedir, 'mri', 'T1.mgz')
    exts    = fslimage.ALLOWED_EXTENSIONS + fslmgh.ALLOWED_EXTENSIONS

    try:
        return fslpath.addExt(t1, allowedExts=exts, mustExist=True)
    except fslpath.PathError:
        return None
