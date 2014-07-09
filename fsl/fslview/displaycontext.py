#!/usr/bin/env python
#
# displaycontext.py - Classes which define how images should be displayed.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#

import numpy         as np
import matplotlib.cm as mplcm

import props
import fsl.data.image as fslimage


class ImageDisplay(props.HasProperties):
    """A class which describes how an :class:`~fsl.data.image.Image`  should
    be displayed.

    This class doesn't have any functionality - it is up to things which
    actually display an :class:`~fsl.data.image.Image` to adhere to the
    properties stored in the associated :class:`ImageDisplay` object.
    """

    
    enabled = props.Boolean(default=True)
    """Should this image be displayed at all?"""

    
    alpha = props.Real(minval=0.0, maxval=1.0, default=1.0)
    """Transparency - 1.0 is fully opaque, and 0.0 is fully transparent."""

    
    displayRange = props.Bounds(ndims=1,
                                editLimits=True,
                                labels=['Min.', 'Max.'])
    """Image values which map to the minimum and maximum colour map colours."""

    
    samplingRate = props.Int(minval=1, maxval=16, default=1, clamped=True)
    """Only display every Nth voxel (a performance tweak)."""

    
    rangeClip = props.Boolean(default=False)
    """If ``True``, don't display voxel values which are beyond the
    :attr:`displayRange`.
    """

    
    cmap = props.ColourMap(default=mplcm.Greys_r)
    """The colour map, a :class:`matplotlib.colors.Colourmap` instance."""

    
    volume = props.Int(minval=0, maxval=0, default=0, clamped=True)
    """If a 4D image, the current volume to display."""


    transform = fslimage.Image.transform
    """How the image is transformed from voxel to real world coordinates.
    This property is bound to the :attr:`~fsl.data.image.Image.transform`
    property of the image associated with this :class:`ImageDisplay`.
    """

    
    name = fslimage.Image.name
    """The image name.  This property is bound to the
    :attr:`~fsl.data.image.Image.name` property.
    """

    
    def is4DImage(self):
        """Returns ``True`` if this image is 4D, ``False`` otherwise.
        """
        return self.image.is4DImage()

        
    _view = props.VGroup(('name',
                          'enabled',
                          'displayRange',
                          'alpha',
                          'rangeClip',
                          'samplingRate',
                          'transform',
                          'cmap'))

    
    _labels = {
        'name'         : 'Image name',
        'enabled'      : 'Enabled',
        'displayRange' : 'Display range',
        'alpha'        : 'Opacity',
        'rangeClip'    : 'Clipping',
        'samplingRate' : 'Sampling rate',
        'transform'    : 'Image transform',
        'volume'       : 'Volume index',
        'cmap'         : 'Colour map'}

    
    _tooltips = {
        'name'         : 'The name of this image',
        'enabled'      : 'Enable/disable this image',
        'alpha'        : 'Opacity, between 0.0 (transparent) and 1.0 (opaque)',
        'displayRange' : 'Minimum/maximum display values',
        'rangeClip'    : 'Do not show areas of the image which lie '
                         'outside of the display range',
        'samplingRate' : 'Draw every Nth voxel',
        'transform'    : 'The transformation matrix which specifies the '
                         'conversion from voxel coordinates to a real world '
                         'location',
        'volume'       : 'Index of volume to display (for 4D images)',
        'cmap'         : 'Colour map'}

    
    _propHelp = _tooltips


    def __init__(self, image):
        """Create an :class:`ImageDisplay` for the specified image.

        :arg image: A :class:`~fsl.data.image.Image` object.
        """

        self.image = image

        # bind self.transform and self.name to 
        # image.transform/image.name, so changes
        # in one are propagated to the other
        self.bindProps('transform', image)
        self.bindProps('name',      image)

        # Attributes controlling image display. Only
        # determine the real min/max for small images -
        # if it's memory mapped, we have no idea how big
        # it may be! So we calculate the min/max of a
        # sample (either a slice or an image, depending
        # on whether the image is 3D or 4D)
        if np.prod(image.shape) > 2 ** 30:
            sample = image.data[..., image.shape[-1] / 2]
            self.dataMin = float(sample.min())
            self.dataMax = float(sample.max())
        else:
            self.dataMin = float(image.data.min())
            self.dataMax = float(image.data.max())

        dRangeLen = abs(self.dataMax - self.dataMin)

        self.displayRange.setMin(0, self.dataMin - 0.5 * dRangeLen)
        self.displayRange.setMax(0, self.dataMax + 0.5 * dRangeLen)
        self.displayRange.setRange(0, self.dataMin, self.dataMax)

        # is this a 4D volume?
        if image.is4DImage():
            self.setConstraint('volume', 'maxval', image.shape[3] - 1)


class DisplayContext(props.HasProperties):
    """Contains a number of properties defining how an
    :class:`~fsl.dat.aimage.ImageList` is to be displayed.
    """

    
    selectedImage = props.Int(minval=0, default=0, clamped=True)
    """Index of the currently 'selected' image. 

    If you're interested in the currently selected image, you must also listen
    for changes to the :attr:`fsl.data.image.ImageList.images` list as, if the
    list changes, the :attr:`selectedImage` index may not change, but the
    image to which it points may be different.
    """


    location = props.Point(ndims=3, labels=('X', 'Y', 'Z'))
    """The location property contains the currently selected
    3D location (xyz) in the image list space. 
    """


    volume = props.Int(minval=0, maxval=0, default=0, clamped=True)
    """The volume property contains the currently selected volume
    across the 4D images in the :class:`~fsl.data.image/ImageList`.
    This property may not be relevant to all images in the image list
    (i.e. it is meaningless for 3D images).
    """


    def __init__(self, imageList):
        """Create a :class:`DisplayContext` object.

        :arg imageList: A :class:`~fsl.data.image.ImageList` instance.
        """
        
        self._imageList = imageList
        self._name = '{}_{}'.format(self.__class__.__name__, id(self))

        self._imageListChanged()

        # initialise the location to be
        # the centre of the image world
        b = imageList.bounds
        self.location.xyz = [
            b.xlo + b.xlen / 2.0,
            b.ylo + b.ylen / 2.0,
            b.zlo + b.zlen / 2.0] 

        imageList.addListener('images', self._name, self._imageListChanged)
        self.addListener(     'volume', self._name, self._volumeChanged)


    def _imageListChanged(self, *a):
        """Called when the :attr:`fsl.data.image.ImageList.images` property
        changes.

        Ensures that an :class:`ImageDisplay` object exists for every image,
        and updates the constraints on the :attr:`selectedImage` and
        :attr:`volume` properties.
        """

        nimages = len(self._imageList)

        # Ensure that an ImageDisplay
        # object exists for every image
        for image in self._imageList:
            try:             image.getAttribute('display')
            except KeyError: image.setAttribute('display', ImageDisplay(image))

        # Limit the selectedImage property
        # so it cannot take a value greater
        # than len(imageList)-1
        if nimages > 0:
            self.setConstraint('selectedImage', 'maxval', nimages - 1)
        else:
            self.setConstraint('selectedImage', 'maxval', 0)

        # Limit the volume property so it
        # cannot take a value greater than
        # the longest 4D volume in the
        # image list
        maxvols = 0

        for image in self._imageList:

            if not image.is4DImage(): continue

            if image.shape[3] > maxvols:
                maxvols = image.shape[3]

        if maxvols > 0:
            self.setConstraint('volume', 'maxval', maxvols - 1)
        else:
            self.setConstraint('volume', 'maxval', 0)


    def _volumeChanged(self, *a):
        """Called when the :attr:`volume` property changes.

        Propagates the change on to the :attr:`ImageDisplay.volume` property
        for each image in the :class:`~fsl.data.image.ImageList`.
        """
        for image in self._imageList:
            
            # The volume property for each image should
            # be clamped to the possible value for that
            # image, so we don't need to check if the
            # current volume value is valid for each image
            image.getAttribute('display').volume = self.volume

            
    def _imageListBoundsChanged(self, *a):
        """Called when the :attr:`fsl.data.image.ImageList.bounds` property
        changes.

        Updates the constraints on the :attr:`location` property.
        """
        bounds = self._imageList.bounds

        self.location.setLimits(0, bounds.xlo, bounds.xhi)
        self.location.setLimits(1, bounds.ylo, bounds.yhi)
        self.location.setLimits(2, bounds.zlo, bounds.zhi)