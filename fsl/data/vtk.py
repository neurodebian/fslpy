#!/usr/bin/env python
#
# vtk.py - The VTKMesh class.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides the :class:`VTKMesh` class, for loading triangle
meshes from VTK files.

A handful of convenience functions are also in this module:

.. autosummary::
   :nosignatures:

   loadVTKPolyDataFile
   getFIRSTPrefix
   findReferenceImage


.. note:: I/O support is very limited - currently, the only supported file
          type is the VTK legacy file format, containing the ``POLYDATA``
          dataset. the :class:`TriangleMesh` class assumes that every polygon
          defined in an input file is a triangle (i.e. refers to three
          vertices).

          See http://www.vtk.org/wp-content/uploads/2015/04/file-formats.pdf
          for an overview of the VTK legacy file format.

          In the future, I may or may not add support for more complex meshes.
"""


import os.path as op

import numpy as np

import fsl.data.mesh  as fslmesh
import fsl.data.image as fslimage


ALLOWED_EXTENSIONS     = ['.vtk']
"""A list of file extensions which could contain :class:`VTKMesh` data.
"""


EXTENSION_DESCRIPTIONS = ['VTK polygon model file']
"""A description for each of the extensions in :data:`ALLOWED_EXTENSIONS`."""


class VTKMesh(fslmesh.Mesh):
    """The ``VTKMesh`` class represents a triangle mesh loaded from a VTK
    file. Typically only one set of vertices will be associated with a
    ``VTKMesh``.
    """


    def __init__(self, infile, fixWinding=False):
        """Create a ``VTKMesh``.

        :arg infile:     VTK file to load mesh from.
        :arg fixWinding: See the :meth:`.Mesh.addVertices` method.
        """

        data, lengths, indices = loadVTKPolydataFile(infile)
        name                   = op.basename(infile)
        dataSource             = op.abspath(infile)

        if np.any(lengths != 3):
            raise RuntimeError('All polygons in VTK file must be '
                               'triangles ({})'.format(infile))

        fslmesh.Mesh.__init__(self,
                              indices,
                              name,
                              dataSource,
                              vertices=data,
                              fixWinding=fixWinding)


def loadVTKPolydataFile(infile):
    """Loads a vtk legacy file containing a ``POLYDATA`` data set.

    :arg infile: Name of a file to load from.

    :returns: a tuple containing three values:

                - A :math:`N\\times 3` ``numpy`` array containing :math:`N`
                  vertices.
                - A 1D ``numpy`` array containing the lengths of each polygon.
                - A 1D ``numpy`` array containing the vertex indices for all
                  polygons.
    """

    lines = None

    with open(infile, 'rt') as f:
        lines = f.readlines()

    lines = [l.strip() for l in lines]

    if lines[3] != 'DATASET POLYDATA':
        raise ValueError('Only the POLYDATA data type is supported')

    nVertices = int(lines[4].split()[1])
    nPolygons = int(lines[5 + nVertices].split()[1])
    nIndices  = int(lines[5 + nVertices].split()[2]) - nPolygons

    vertices       = np.zeros((nVertices, 3), dtype=np.float32)
    polygonLengths = np.zeros( nPolygons,     dtype=np.uint32)
    indices        = np.zeros( nIndices,      dtype=np.uint32)

    for i in range(nVertices):
        vertLine       = lines[i + 5]
        vertices[i, :] = [float(w) for w in vertLine.split()]

    indexOffset = 0
    for i in range(nPolygons):

        polyLine          = lines[6 + nVertices + i].split()
        polygonLengths[i] = int(polyLine[0])

        start              = indexOffset
        end                = indexOffset + polygonLengths[i]
        indices[start:end] = [int(w) for w in polyLine[1:]]

        indexOffset        += polygonLengths[i]

    return vertices, polygonLengths, indices


def getFIRSTPrefix(modelfile):
    """If the given ``vtk`` file was generated by `FIRST
    <https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FIRST>`_, this function
    will return the file prefix. Otherwise a ``ValueError`` will be
    raised.
    """

    if not modelfile.endswith('first.vtk'):
        raise ValueError('Not a first vtk file: {}'.format(modelfile))

    modelfile = op.basename(modelfile)
    prefix    = modelfile.split('-')
    prefix    = '-'.join(prefix[:-1])

    return prefix


def findReferenceImage(modelfile):
    """Given a ``vtk`` file, attempts to find a corresponding ``NIFTI``
    image file. Return the path to the image, or ``None`` if no image was
    found.

    Currently this function will only return an image for ``vtk`` files
    generated by `FIRST <https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FIRST>`_.
    """

    try:

        dirname  = op.dirname(modelfile)
        prefixes = [getFIRSTPrefix(modelfile)]
    except ValueError:
        return None

    if prefixes[0].endswith('_first'):
        prefixes.append(prefixes[0][:-6])

    for p in prefixes:
        try:
            return fslimage.addExt(op.join(dirname, p), mustExist=True)
        except fslimage.PathError:
            continue

    return None
