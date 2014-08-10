#!/usr/bin/env python
#
# glimagedata.py - Create OpenGL data to render 2D slices of a 3D image.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""A GLImageData object encapsulates the OpenGL information necessary
 to render 2D slices of a 3D image, in an OpenGL 2.1 compatible manner.

A slice from one image is rendered using two buffers and two textures.

The first buffer, the 'world coordinate buffer' contains the 2D X/Y
coordinates (single precision floating point, X and Y respectively correspond
to the screen horizontal and vertical axes), in world space, for every voxel
to be displayed. Each voxel is represented by four vertices, of four vertices,
which are rendered as quads.

The next buffer, the 'texture coordinate buffer' contains the, 2D X/Y
coordinates in world space, of the center of each of those voxels. This
duplication is an unfortunate necessity at this point in time. These
coordinates are used to calculate the value at each of the rendered voxels.
The vertex shader takes these world X/Y coordinates along with the Z
coordinate of the currently displayed slice, transforms them into voxel
coordinates using the :attr:`fsl.data.image.worldToVoxMat` transformation
matrix, and uses these voxel coordinates to look up the value in the 3D
image texture.

The image data itself is stored as a 3D texture. Data for signed or
unsigned 8 or 16 bit integer images is stored on the GPU in the same
format; all other data types are stored as 32 bit floating point.

Finally, a 1D texture is used is used to store a lookup table containing
an RGBA8 colour map, to colour each voxel according to its value.

All of these things are created when a GLImageData object is
instantiated. They are available as attributes of the object:

 - imageBuffer
 - worldCoordBuffer
 - texCoordBuffer
 - imageBuffer
 - colourBuffer
 - nVertices

The contents of all of these buffers is is dependent upon the way that
the image is being displayed.  They are regenerated automatically when
the image display properties are changed (via listeners registered on
the relevant fsl.fslview.displaycontext.ImageDisplay properties).

If the display orientation changes (i.e. the image dimensions that map
to the screen X/Y axes) the genVertexData method must be called
manually, to regenerate the voxel indices.

"""

import logging
log = logging.getLogger(__name__)

import numpy as np

import OpenGL.GL         as gl
import OpenGL.arrays.vbo as vbo

# This extension provides some texture data format identifiers
# which are standard in more modern OpenGL versions.
import OpenGL.GL.ARB.texture_rg as arbrg

import fsl.fslview.gl.glimage as glimage


class GLImageData(object):

    def __init__(self, image, xax, yax, imageDisplay):
        """
        Initialise the OpenGL data buffers required to render the given image.
        Parameters:
        
          - image:        A fsl.data.image.Image object.
        
          - xax:          The image axis which maps to the screen x axis.
        
          - yax:          The image axis which maps to the screen y axis.
        
          - imageDisplay: A fsl.fslview.displaycontext.ImageDisplay object
                          which describes how the image is to be displayed.
        """
        
        self.image   = image
        self.display = imageDisplay

        self._checkDataType()

        # Buffers for storing image data
        # and voxel coordinates
        self.imageBuffer = self._genImageBuffer()
        self.genVertexData(xax, yax)

        # The colour buffer, containing a map of
        # colours (stored on the GPU as a 1D texture)
        # This is initialised in the updateColourBuffer
        # method
        self.colourTexture = gl.glGenTextures(1) 
        self.genColourTexture()

        # Add listeners to this image so the view can be
        # updated when its display properties are changed
        self._configDisplayListeners()


    def genVertexData(self, xax, yax):
        """
        """

        self.xax = xax
        self.yax = yax

        worldCoords, texCoords = glimage.genVertexData(
            self.image, self.display, xax, yax)

        worldCoords = worldCoords[:, [xax, yax]]
        texCoords   = texCoords[  :, [xax, yax]]

        worldCoordBuffer = vbo.VBO(worldCoords.ravel('C'), gl.GL_STATIC_DRAW)
        texCoordBuffer   = vbo.VBO(texCoords  .ravel('C'), gl.GL_STATIC_DRAW)

        self.worldCoordBuffer = worldCoordBuffer
        self.texCoordBuffer   = texCoordBuffer
        self.nVertices        = worldCoords.shape[0]

        
    def _checkDataType(self):
        """
        This method determines the appropriate OpenGL texture data
        format to use for the image managed by this GLImageData
        object. 
        """

        dtype = self.image.data.dtype

        if   dtype == np.uint8:  self.texExtFmt = gl.GL_UNSIGNED_BYTE
        elif dtype == np.int8:   self.texExtFmt = gl.GL_UNSIGNED_BYTE
        elif dtype == np.uint16: self.texExtFmt = gl.GL_UNSIGNED_SHORT
        elif dtype == np.int16:  self.texExtFmt = gl.GL_UNSIGNED_SHORT
        elif dtype == np.uint32: self.texExtFmt = gl.GL_UNSIGNED_INT
        elif dtype == np.int32:  self.texExtFmt = gl.GL_UNSIGNED_INT
        else:                    self.texExtFmt = gl.GL_FLOAT

        if   dtype == np.uint8:  self.texIntFmt = gl.GL_INTENSITY
        elif dtype == np.int8:   self.texIntFmt = gl.GL_INTENSITY
        elif dtype == np.uint16: self.texIntFmt = gl.GL_INTENSITY
        elif dtype == np.int16:  self.texIntFmt = gl.GL_INTENSITY
        elif dtype == np.uint32: self.texIntFmt = gl.GL_INTENSITY
        elif dtype == np.int32:  self.texIntFmt = gl.GL_INTENSITY
        else:                    self.texIntFmt = arbrg.GL_R32F

        if   dtype == np.int8:   self.signed = True
        elif dtype == np.int16:  self.signed = True
        elif dtype == np.int32:  self.signed = True
        else:                    self.signed = False

        if   dtype == np.uint8:  normFactor = 255.0
        elif dtype == np.int8:   normFactor = 255.0
        elif dtype == np.uint16: normFactor = 65535.0
        elif dtype == np.int16:  normFactor = 65535.0
        elif dtype == np.uint32: normFactor = 4294967295.0
        elif dtype == np.int32:  normFactor = 4294967295.0
        else:                    normFactor = 1.0

        if   dtype == np.int8:   normOffset = 128.0
        elif dtype == np.int16:  normOffset = 32768.0
        elif dtype == np.int32:  normOffset = 2147483648.0
        else:                    normOffset = 0.0

        xform = np.identity(4)
        xform[0, 0] =  normFactor
        xform[0, 3] = -normOffset

        self.dataTypeXform = xform.transpose()

        log.debug('Image {} (data type {}) is to be '
                  'stored as a 3D texture with '
                  'internal format {}, external format {}, '
                  'norm factor {}, norm offset {}'.format(
                      self.image.name,
                      dtype,
                      self.texIntFmt,
                      self.texExtFmt,
                      normFactor,
                      normOffset))

        
    def _genImageBuffer(self):
        """
        (Re-)Generates the OpenGL image texture used to store the data for the
        given image. The buffer is stored as an attribute of the image and, if
        it has already been created (e.g. by another GLImageData object), the
        existing buffer is returned.
        """

        image   = self.image
        display = self.display
        volume  = display.volume

        if display.interpolation: interp = gl.GL_LINEAR
        else:                     interp = gl.GL_NEAREST

        # we only store a single 3D image
        # in GPU memory at any one time
        if len(image.shape) > 3: imageData = image.data[:, :, :, volume]
        else:                    imageData = image.data

        # Check to see if the image buffer
        # has already been created
        try:
            displayHash, imageBuffer = image.getAttribute('glImageBuffer')
        except:
            displayHash = None
            imageBuffer = None

        if imageBuffer is None:
            imageBuffer = gl.glGenTextures(1)

        # The image buffer already exists, and it
        # contains the data for the requested volume.  
        elif displayHash == hash(display):
            return imageBuffer

        log.debug('Populating texture buffer for '
                  'image {} (data shape: {})'.format(
                      image.name,
                      imageData.shape))

        # The image data is flattened, with fortran dimension
        # ordering, so the data, as stored on the GPU, has its
        # first dimension as the fastest changing.
        imageData = imageData.ravel(order='F')

        # Enable storage of tightly packed data of any size (i.e.
        # our texture shape does not have to be divisible by 4).
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT,   1)
        
        # Set up image texture sampling thingos
        gl.glBindTexture(gl.GL_TEXTURE_3D, imageBuffer)
        gl.glTexParameteri(gl.GL_TEXTURE_3D,
                           gl.GL_TEXTURE_MAG_FILTER,
                           interp)
        gl.glTexParameteri(gl.GL_TEXTURE_3D,
                           gl.GL_TEXTURE_MIN_FILTER,
                           interp)
        gl.glTexParameteri(gl.GL_TEXTURE_3D,
                           gl.GL_TEXTURE_WRAP_S,
                           gl.GL_CLAMP_TO_BORDER)
        gl.glTexParameteri(gl.GL_TEXTURE_3D,
                           gl.GL_TEXTURE_WRAP_T,
                           gl.GL_CLAMP_TO_BORDER)
        gl.glTexParameteri(gl.GL_TEXTURE_3D,
                           gl.GL_TEXTURE_WRAP_R,
                           gl.GL_CLAMP_TO_BORDER)
        gl.glTexParameterfv(gl.GL_TEXTURE_3D,
                            gl.GL_TEXTURE_BORDER_COLOR,
                            [0, 0, 0, 0])

        gl.glTexImage3D(gl.GL_TEXTURE_3D,
                        0,
                        self.texIntFmt,
                        image.shape[0], image.shape[1], image.shape[2],
                        0,
                        gl.GL_RED,
                        self.texExtFmt,
                        imageData)

        # Add the ImageDisplay hash, and a reference to the
        # texture as an attribute of the image, so other
        # things which want to render the same volume of the
        # image don't need to duplicate all of that data.
        image.setAttribute('glImageBuffer', (hash(display), imageBuffer))

        return imageBuffer

        
    def genColourTexture(self):
        """
        Regenerates the colour texture used to colour image voxels.
        """

        texCoordXform = glimage.genColourTexture(self.image,
                                                 self.display,
                                                 self.colourTexture,
                                                 xform=self.dataTypeXform)
        self.texCoordXform = texCoordXform


    def _configDisplayListeners(self):
        """
        Adds a bunch of listeners to the image.ImageDisplay object which
        defines how the given image is to be displayed. This is done so we
        can update the colour texture when image display properties are
        changed. 
        """

        def vertexUpdate(*a):
            self.genVertexData(self.xax, self.yax)

        def imageUpdate(*a):
            self._genImageBuffer()
        
        def colourUpdate(*a):
            self.genColourTexture()

        display = self.display
        lnrName = 'GlImageData_{}'.format(id(self))

        display.addListener('transform',       lnrName, vertexUpdate)
        display.addListener('interpolation',   lnrName, imageUpdate)
        display.addListener('alpha',           lnrName, colourUpdate)
        display.addListener('displayRange',    lnrName, colourUpdate)
        display.addListener('clipLow',         lnrName, colourUpdate)
        display.addListener('clipHigh',        lnrName, colourUpdate)
        display.addListener('cmap',            lnrName, colourUpdate)
        display.addListener('voxelResolution', lnrName, vertexUpdate)
        display.addListener('worldResolution', lnrName, vertexUpdate)
        display.addListener('volume',          lnrName, imageUpdate)
