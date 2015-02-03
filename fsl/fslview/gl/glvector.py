#!/usr/bin/env python
#
# glvector.py - OpenGL vertex creation and rendering code for drawing a
# X*Y*Z*3 image as a vector.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""Defines the :class:`GLVector` class, which encapsulates the logic for
rendering 2D slices of a ``X*Y*Z*3`` image as a vector. The ``GLVector`` class
provides the interface defined by the
:class:`~fsl.fslview.gl.globject.GLObject` class.

A ``GLVector`` instance may be used to render an
:class:`~fsl.data.image.Image` instance which has an ``imageType`` of
``vector``. It is assumed that this ``Image`` instance is associated with
a :class:`~fsl.fslview.displaycontext.display.Display` instance which contains
a :class:`~fsl.fslview.dislpaycontext.vectoropts.VectorOpts` instance,
containing options specific to vector rendering.

Vectors can be displayed in one of several 'modes', defined by the
``VectorOpts.displayMode`` option:

 - ``rgb``: The magnitude of the vector at each voxel along each axis is
            displayed as a combination of three colours. 

 - `line``: The vector at each voxel is rendered as an undirected line.

The :class:`GLVector` class makes use of the functions defined in the
:mod:`fsl.fslview.gl.gl14.glvector_funcs` or the
:mod:`fsl.fslview.gl.gl21.glvector_funcs` modules, which provide OpenGL 
version specific details for creation/storage of vertex data, and for
rendering.

These version dependent modules must provide the following functions:

 - ``init(GLVector)``:  Initialise any necessary OpenGL shaders, textures,
   buffers, etc.

 - ``destroy(GLVector)``: Clean up any OpenGL data/state.

 - ``setAxes(GLVector)``: Create the necessary geometry, ensuring that it is
    oriented in such a way as to be displayed with ``GLVector.xax`` mapping to
    the horizontal screen axis, ``GLVector.yax`` to the vertical axis, and
    ``GLVector.yax`` to the depth axis.

 - ``preDraw(GLVector)``: Prepare GL state ready for drawing.

 - ``draw(GLVector, zpos, xform=None)``: Draw a slice of the vector image
   at the given ``zpos``.
                                    
 - ``postDraw(GLVector)``: Clean up GL state after drawing.


The vector image is stored on the GPU as a 3D RGB texture, where the ``R``
channel contains the ``x`` vector values, the ``G`` channel the ``y`` values,
and the ``B`` channel the ``z`` values. In ``line`` mode, this 3D texture
contains the vector data normalised, but unchanged. However, in ``rgb`` mode,
the absolute vaues of the vector data are stored. This is necessary to
allow for GPU based interpolation of RGB vector images.

In both ``rgb`` and ``line`` mode, three 1D textures are used to store a
colour table for each of the ``x``, ``y`` and ``z`` components. A custom
fragment shader program looks up the ``xyz`` vector values, looks up colours
for each of them, and combines the three colours to form the final fragment
colour.

When in ``rgb`` mode, 2D slices of the image are rendered using a simple
rectangular slice through the texture. When in ``line`` mode, each voxel
is rendered using two vertices, which are aligned in the direction of the
vector.

The colour of each vector may be modulated by another image, specified by the
:attr:`~fsl.fslview.displaycontext.vectoropts.VectorOpts.modulate` property.
This modulation image is stored as a 3D single-channel texture.
"""

import numpy                   as np
import OpenGL.GL               as gl

import fsl.data.image          as fslimage
import fsl.fslview.gl          as fslgl
import fsl.fslview.gl.textures as fsltextures
import fsl.fslview.gl.globject as globject


def _lineModePrefilter(data):
    """Prefilter method for the vector image texture, when it is being
    displayed in ``line`` mode - see
    :meth:`~fsl.fslview.gl.textures.ImageTexture.setPrefilter`.
    """
    return data.transpose((3, 0, 1, 2))


def _rgbModePrefilter(data):
    """Prefilter method for the vector image texture, when it is being
    displayed in ``rgb`` mode.
    """ 
    return np.abs(data.transpose((3, 0, 1, 2)))


class GLVector(globject.GLObject):
    """The :class:`GLVector` class encapsulates the data and logic required
    to render 2D slices of a ``X*Y*Z*3`` image as vectors.
    """

    def __init__(self, image, display):
        """Create a :class:`GLVector` object bound to the given image and
        display.

        :arg image:        A :class:`~fsl.data.image.Image` object.
        
        :arg imageDisplay: A :class:`~fsl.fslview.displaycontext.Display`
                           object which describes how the image is to be
                           displayed .
        """

        if not image.is4DImage() or image.shape[3] != 3:
            raise ValueError('Image must be 4 dimensional, with 3 volumes '
                             'representing the XYZ vector angles')

        globject.GLObject.__init__(self, image, display)
        self._ready = False

        
    def init(self):
        """Initialise the OpenGL data required to render the given image.

        This method does the following:
        
          - Creates the image texture, the modulate texture, and the three
            colour map textures.

          - Adds listeners to the
            :class:`~fsl.fslview.displaycontext.display.Display` and
            :class:`~fsl.fslview.displaycontext.vectoropts.VectorOpts`
            instances, so the textures and geometry can be updated when
            necessary.

          - Calls the GTL version specific ``glvector_funcs.init`` function.
        """

        display = self.display
        opts    = self.displayOpts
        name    = self.name

        self.xColourTexture = gl.glGenTextures(1)
        self.yColourTexture = gl.glGenTextures(1)
        self.zColourTexture = gl.glGenTextures(1)
        self.modTexture     = None
        self.imageTexture   = None
        
        def modUpdate( *a):
            self.refreshModulateTexture()

        def cmapUpdate(*a):
            self.refreshColourTextures()

        def modeChange(*a):
            self._onModeChange()

        def coordUpdate(*a):
            self.setAxes(self.xax, self.yax)

        display.addListener('alpha',       name, cmapUpdate)
        display.addListener('transform',   name, coordUpdate)
        display.addListener('resolution',  name, coordUpdate) 
        opts   .addListener('xColour',     name, cmapUpdate)
        opts   .addListener('yColour',     name, cmapUpdate)
        opts   .addListener('zColour',     name, cmapUpdate)
        opts   .addListener('suppressX',   name, cmapUpdate)
        opts   .addListener('suppressY',   name, cmapUpdate)
        opts   .addListener('suppressZ',   name, cmapUpdate)
        opts   .addListener('modulate',    name, modUpdate)
        opts   .addListener('displayMode', name, modeChange)

        if   opts.displayMode == 'line': prefilter = _lineModePrefilter
        elif opts.displayMode == 'rgb':  prefilter = _rgbModePrefilter

        self.imageTexture = fsltextures.getTexture(
            self.image,
            type(self).__name__,
            display=self.display,
            nvals=3,
            normalise=True,
            prefilter=prefilter) 

        self.refreshModulateTexture()
        self.refreshColourTextures()

        fslgl.glvector_funcs.init(self)
        
        self._ready = True

        
    def destroy(self):
        """Deletes the GL textures, deregisters the listeners
        configured in :meth:`init`, and calls the GL version specific
        ``glvector_funcs.destroy`` function.
        """

        gl.glDeleteTextures(self.xColourTexture)
        gl.glDeleteTextures(self.yColourTexture)
        gl.glDeleteTextures(self.zColourTexture)

        fsltextures.deleteTexture(self.imageTexture)
        fsltextures.deleteTexture(self.modTexture) 

        self.display    .removeListener('alpha',       self.name)
        self.display    .removeListener('transform',   self.name)
        self.display    .removeListener('resolution',  self.name)
        self.displayOpts.removeListener('xColour',     self.name)
        self.displayOpts.removeListener('yColour',     self.name)
        self.displayOpts.removeListener('zColour',     self.name)
        self.displayOpts.removeListener('suppressX',   self.name)
        self.displayOpts.removeListener('suppressY',   self.name)
        self.displayOpts.removeListener('suppressZ',   self.name)
        self.displayOpts.removeListener('modulate',    self.name)
        self.displayOpts.removeListener('displayMode', self.name)

        fslgl.glvector_funcs.destroy(self)

        
    def ready(self):
        """Returns `True` when the OpenGL data/state has been initialised,
        and the image is ready to be drawn, `False` before.
        """ 
        return self._ready


    def _onModeChange(self, *a):
        """Called when the
        :attr:`~fsl.fslview.displaycontext.vectoropts.VectorOpts.displayMode`
        property changes.

        Initialises data and GL state for the newly selected vector display
        mode.
        """

        mode = self.displayOpts.displayMode

        # Disable atexture interpolation in line mode
        if mode == 'line':
            
            if self.display.interpolation != 'none':
                self.display.interpolation = 'none'
                
            self.display.disableProperty('interpolation')
            
        elif mode == 'rgb':
            self.display.enableProperty('interpolation')

        if   mode == 'line': prefilter = _lineModePrefilter
        elif mode == 'rgb':  prefilter = _rgbModePrefilter 
            
        fslgl.glvector_funcs.destroy(self)
        self.imageTexture.setPrefilter(prefilter)
        fslgl.glvector_funcs.init(self)
        self.setAxes(self.xax, self.yax)
        

    def refreshModulateTexture(self):
        """Called when the
        :attr`~fsl.fslview.displaycontext.vectoropts.VectorOpts.modulate`
        property changes.

        Reconfigures the modulation texture. If no modulation image is
        selected, a 'dummy' texture is creatad, which contains all white
        values (and which result in the modulation texture having no effect).
        """

        modImage = self.displayOpts.modulate

        if self.modTexture is not None:
            fsltextures.deleteTexture(self.modTexture)

        if modImage == 'none':
            textureData = np.zeros((5, 5, 5), dtype=np.uint8)
            textureData[:] = 255
            modImage   = fslimage.Image(textureData)
            modDisplay = None
            norm       = False
            
        else:
            modDisplay = self.display
            norm       = True

        self.modTexture = fsltextures.getTexture(
            modImage,
            '{}_{}_modulate'.format(type(self).__name__, id(self.image)),
            display=modDisplay,
            normalise=norm)


    def refreshColourTextures(self, colourRes=256):
        """Called when the component colour maps need to be updated, when
        one of the
        :attr:`~fsl.fslview.displaycontext.vectoropts.VectorOpts.xColour`,
        ``yColour``, ``zColour``, ``suppressX``, ``suppressY``, or
        ``suppressZ`` properties change.

        Regenerates the colour textures.
        """

        xcol = self.displayOpts.xColour + [1.0]
        ycol = self.displayOpts.yColour + [1.0]
        zcol = self.displayOpts.zColour + [1.0]

        xsup = self.displayOpts.suppressX
        ysup = self.displayOpts.suppressY
        zsup = self.displayOpts.suppressZ 

        xtex = self.xColourTexture
        ytex = self.yColourTexture
        ztex = self.zColourTexture

        for colour, texture, suppress in zip(
                (xcol, ycol, zcol),
                (xtex, ytex, ztex),
                (xsup, ysup, zsup)):

            if not suppress:
                
                cmap = np.array(
                    [np.linspace(0.0, i, colourRes) for i in colour])
            else:
                cmap = np.zeros((4, colourRes))

            # Component magnitudes
            # of 0 are transparent
            cmap[3, :] = 1.0
            cmap[3, 0] = 0.0

            cmap = np.array(np.floor(cmap * 255), dtype=np.uint8).ravel('F')

            gl.glBindTexture(gl.GL_TEXTURE_1D, texture)
            gl.glTexParameteri(gl.GL_TEXTURE_1D,
                               gl.GL_TEXTURE_MAG_FILTER,
                               gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_1D,
                               gl.GL_TEXTURE_MIN_FILTER,
                               gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_1D,
                               gl.GL_TEXTURE_WRAP_S,
                               gl.GL_CLAMP_TO_EDGE)

            gl.glTexImage1D(gl.GL_TEXTURE_1D,
                            0,
                            gl.GL_RGBA8,
                            colourRes,
                            0,
                            gl.GL_RGBA,
                            gl.GL_UNSIGNED_BYTE,
                            cmap)

        gl.glBindTexture(gl.GL_TEXTURE_1D, 0)
    

    def setAxes(self, xax, yax):
        """Calls the GL version-specific ``glvector_funcs.setAxes`` function,
        which should make sure that the GL geometry representation is up
        to date.
        """

        self.xax = xax
        self.yax = yax
        self.zax = 3 - xax - yax

        fslgl.glvector_funcs.setAxes(self)

        
    def preDraw(self):
        """Ensures that the five textures (the vector and modulation images,
        and the three colour textures) are bound, then calls
        ``glvector_funcs.preDraw``.
        """
        if not self.display.enabled:
            return

        gl.glEnable(gl.GL_TEXTURE_1D)
        gl.glEnable(gl.GL_TEXTURE_3D)

        gl.glEnableClientState(gl.GL_VERTEX_ARRAY)

        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.imageTexture.texture)

        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.modTexture.texture) 

        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_1D, self.xColourTexture)

        gl.glActiveTexture(gl.GL_TEXTURE3)
        gl.glBindTexture(gl.GL_TEXTURE_1D, self.yColourTexture)

        gl.glActiveTexture(gl.GL_TEXTURE4)
        gl.glBindTexture(gl.GL_TEXTURE_1D, self.zColourTexture) 
 
        fslgl.glvector_funcs.preDraw(self)

        
    def draw(self, zpos, xform=None):
        """Calls the ``glvector_funcs.draw`` function. """
        
        if not self.display.enabled:
            return
        
        fslgl.glvector_funcs.draw(self, zpos, xform)

        
    def postDraw(self):
        """Unbindes the five GL textures, and calls the
        ``glvector_funcs.postDraw`` function.
        """
        if not self.display.enabled:
            return

        gl.glDisableClientState(gl.GL_VERTEX_ARRAY)

        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_3D, 0)

        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_3D, 0)

        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_1D, 0)

        gl.glActiveTexture(gl.GL_TEXTURE3)
        gl.glBindTexture(gl.GL_TEXTURE_1D, 0)

        gl.glActiveTexture(gl.GL_TEXTURE4)
        gl.glBindTexture(gl.GL_TEXTURE_1D, 0)    

        gl.glDisable(gl.GL_TEXTURE_1D) 
        gl.glDisable(gl.GL_TEXTURE_3D) 
        
        fslgl.glvector_funcs.postDraw(self) 