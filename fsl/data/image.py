#!/usr/bin/env python
# 
# image.py - Classes for representing 3D/4D images and collections of said
# images.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""Classes for representing 3D/4D images and collections of said images.

See the :mod:`fsl.data.imageio` module for image loading/saving 
functionality.

"""

import logging
import collections
import os.path as op

import numpy   as np
import nibabel as nib

import props

import fsl.utils.transform as transform
import fsl.data.imageio    as iio
import fsl.data.constants  as constants


log = logging.getLogger(__name__)



class Image(props.HasProperties):
    """Class which represents a 3D/4D image. Internally, the image is
    loaded/stored using :mod:`nibabel`.

    Arbitrary data may be associated with an :class:`Image` object, via the
    :meth:`getAttribute` and :meth:`setAttribute` methods (which are just
    front end wrappers around an internal ``dict`` object).

    In addition to the class-level properties defined below, the following
    attributes are present on an :class:`Image` object:

    :ivar nibImage:       The :mod:`nibabel` image object.

    :ivar shape:          A list/tuple containing the number of voxels
                          along each image dimension.

    :ivar pixdim:         A list/tuple containing the size of one voxel
                          along each image dimension.

    :ivar voxToWorldMat:  A 4*4 array specifying the affine transformation
                          for transforming voxel coordinates into real world
                          coordinates.

    :ivar worldToVoxMat:  A 4*4 array specifying the affine transformation
                          for transforming real world coordinates into voxel
                          coordinates.

    :ivar imageFile:      The name of the file that the image was loaded from.

    :ivar tempFile:       The name of the temporary file which was created (in
                          the event that the image was large and was gzipped -
                          see :func:`_loadImageFile`).
    """


    imageType = props.Choice(
        collections.OrderedDict([
            ('volume', '3D/4D volume'),
            ('mask',   '3D/4D mask image'),
            ('vector', '3-direction vector image')]),
        default='volume')
    """This property defines the type of image data."""


    name = props.String()
    """The name of this image."""


    data = props.Object()
    """The image data. This is a read-only :mod:`numpy` array - all changes
       to the image data must be via the :meth:`applyChange` method.
    """


    saved = props.Boolean(default=False)
    """A read-only property (not enforced) which is ``True`` if the image,
    as stored in memory, is saved to disk, ``False`` otherwise.
    """


    def __init__(self,
                 image,
                 xform=None,
                 name=None,
                 header=None,
                 loadData=True):
        """Initialise an Image object with the given image data or file name.

        :arg image:    A string containing the name of an image file to load, 
                       or a :mod:`numpy` array, or a :mod:`nibabel` image
                       object.

        :arg xform:    A ``4*4`` affine transformation matrix which transforms
                       voxel coordinates into real world coordinates.

        :arg name:     A name for the image.

        :arg header:   If not ``None``, assumed to be a
                       :class:`nibabel.nifti1.Nifti1Header` to be used as the 
                       image header. Not applied to images loaded from file,
                       or existing :mod:`nibabel` images.

        :arg loadData: Defaults to ``True``. If ``False``, the image data is
                       not loaded - this is useful if you're only interested
                       in the header data, as the file will be loaded much
                       more quickly. The image data may subsequently be loaded
                       via the :meth:`loadData` method.
        """

        self.nibImage  = None
        self.imageFile = None
        self.tempFile  = None

        if header is not None:
            header = header.copy()

        # The image parameter may be the name of an image file
        if isinstance(image, basestring):
            
            nibImage, filename = iio.loadImage(iio.addExt(image))
            self.nibImage      = nibImage
            self.imageFile     = image

            # if the returned file name is not the same as
            # the provided file name, that means that the
            # image was opened from a temporary file
            if filename != image:
                self.name     = iio.removeExt(op.basename(self.imageFile))
                self.tempFile = nibImage.get_filename()
            else:
                self.name     = iio.removeExt(op.basename(self.imageFile))

            self.saved = True
                
        # Or a numpy array - we wrap it in a nibabel image,
        # with an identity transformation (each voxel maps
        # to 1mm^3 in real world space)
        elif isinstance(image, np.ndarray):

            if xform is None:
                if header is None: xform = np.identity(4)
                else:              xform = header.get_best_affine()
            if name  is None: name = 'Numpy array'
            
            self.nibImage  = nib.nifti1.Nifti1Image(image,
                                                    xform,
                                                    header=header)
            self.name      = name
            
        # otherwise, we assume that it is a nibabel image
        else:
            if name  is None:
                name = 'Nibabel image'
            
            self.nibImage = image
            self.name     = name

        self.shape         = self.nibImage.get_shape()
        self.pixdim        = self.nibImage.get_header().get_zooms()
        self.voxToWorldMat = np.array(self.nibImage.get_affine())
        self.worldToVoxMat = transform.invert(self.voxToWorldMat)

        if loadData:
            self.loadData()
        else:
            self.data = None

        if len(self.shape) < 3 or len(self.shape) > 4:
            raise RuntimeError('Only 3D or 4D images are supported')

        # This dictionary may be used to store
        # arbitrary data associated with this image.
        self._attributes = {}

        
    def loadData(self):
        """Loads the image data from the file. This method only needs to
        be called if the ``loadData`` parameter passed to :meth:`__init__`
        was ``False``.
        """
        self.data = self.nibImage.get_data()
        self.data.flags.writeable = False
        
        
    def applyChange(self, offset, newVals, vol=None):
        """Changes the image data according to the given new values.
        Any listeners registered on the :attr:`data` property will be
        notified of the change.

        :arg offset:  A tuple of three values, containing the xyz
                      offset of the image region to be changed.
        
        :arg newVals: A 3D numpy array containing the new image values.
        
        :arg vol:     If this is a 4D image, the volume index.
        """
        
        if self.is4DImage() and vol is None:
            raise ValueError('Volume must be specified for 4D images')
        
        data          = self.data
        xlo, ylo, zlo = offset
        xhi           = xlo + newVals.shape[0]
        yhi           = ylo + newVals.shape[1]
        zhi           = zlo + newVals.shape[2]

        try:
            data.flags.writeable = True
            if self.is4DImage(): data[xlo:xhi, ylo:yhi, zlo:zhi, vol] = newVals
            else:                data[xlo:xhi, ylo:yhi, zlo:zhi]      = newVals
            data.flags.writeable = False
            
        except:
            data.flags.writeable = False
            raise

        # Force a notification on the 'data' property
        # by assigning its value back to itself
        self.data  = data
        self.saved = False


    def save(self):
        """Convenience method to save any changes made to the :attr:`data` of 
        this :class:`Image` instance.

        See the :func:`fsl.data.imageio.save` function.
        """
        return iio.saveImage(self)
    

    def __hash__(self):
        """Returns a number which uniquely idenfities this :class:`Image`
        object (the result of ``id(self)``).
        """
        return id(self)


    def __str__(self):
        """Return a string representation of this :class:`Image`."""
        return '{}({}, {})'.format(self.__class__.__name__,
                                   self.name,
                                   self.imageFile)

        
    def __repr__(self):
        """See the :meth:`__str__` method."""
        return self.__str__()


    def is4DImage(self):
        """Returns ``True`` if this image is 4D, ``False`` otherwise.
        """
        return len(self.shape) > 3 and self.shape[3] > 1


    def getXFormCode(self):
        """This method returns the code contained in the NIFTI1 header,
        indicating the space to which the (transformed) image is oriented.
        """
        sform_code = self.nibImage.get_header()['sform_code']

        # Invalid values
        if   sform_code > 4: code = constants.NIFTI_XFORM_UNKNOWN
        elif sform_code < 0: code = constants.NIFTI_XFORM_UNKNOWN

        # All is well
        else:                code = sform_code

        return int(code)


    def getWorldOrientation(self, axis):
        """Returns a code representing the orientation of the specified axis
        in world space.

        This method returns one of the following values, indicating the
        direction in which coordinates along the specified axis increase:
          - :attr:`~fsl.data.constants.ORIENT_L2R`:     Left to right
          - :attr:`~fsl.data.constants.ORIENT_R2L`:     Right to left
          - :attr:`~fsl.data.constants.ORIENT_A2P`:     Anterior to posterior
          - :attr:`~fsl.data.constants.ORIENT_P2A`:     Posterior to anterior
          - :attr:`~fsl.data.constants.ORIENT_I2S`:     Inferior to superior
          - :attr:`~fsl.data.constants.ORIENT_S2I`:     Superior to inferior
          - :attr:`~fsl.data.constants.ORIENT_UNKNOWN`: Orientation is unknown

        The returned value is dictated by the XForm code contained in the
        image file header (see the :meth:`getXFormCode` method). Basically,
        if the XForm code is 'unknown', this method will return -1 for all
        axes. Otherwise, it is assumed that the image is in RAS orientation
        (i.e. the X axis increases from left to right, the Y axis increases
        from  posterior to anterior, and the Z axis increases from inferior
        to superior).
        """

        if self.getXFormCode() == constants.NIFTI_XFORM_UNKNOWN:
            return -1

        if   axis == 0: return constants.ORIENT_L2R
        elif axis == 1: return constants.ORIENT_P2A
        elif axis == 2: return constants.ORIENT_I2S

        else: return -1


    def getVoxelOrientation(self, axis):
        """Returns a code representing the (estimated) orientation of the
        specified voxelwise axis.

        See the :meth:`getWorldOrientation` method for a description
        of the return value.
        """
        
        if self.getXFormCode() == constants.NIFTI_XFORM_UNKNOWN:
            return -1 
        
        # the aff2axcodes returns one code for each 
        # axis in the image array (i.e. in voxel space),
        # which denotes the real world direction
        code = nib.orientations.aff2axcodes(
            self.nibImage.get_affine(),
            ((constants.ORIENT_R2L, constants.ORIENT_L2R),
             (constants.ORIENT_A2P, constants.ORIENT_P2A),
             (constants.ORIENT_S2I, constants.ORIENT_I2S)))[axis]
        return code

    
    def getAttribute(self, name):
        """Retrieve the attribute with the given name.

        :raise KeyError: if there is no attribute with the given name.
        """
        return self._attributes[name]

    
    def delAttribute(self, name):
        """Delete and return the value of the attribute with the given name.

        :raise KeyError: if there is no attribute with the given name.
        """
        return self._attributes.pop(name)

        
    def setAttribute(self, name, value):
        """Set an attribute with the given name and the given value."""
        self._attributes[name] = value
        
        log.debug('Attribute set on {}: {} = {}'.format(
            self.name, name, str(value)))


class ImageList(props.HasProperties):
    """Class representing a collection of images to be displayed together.

    Contains a :class:`props.properties_types.List` property containing
    :class:`Image` objects.

    An :class:`ImageList` object has a few wrapper methods around the
    :attr:`images` property, allowing the :class:`ImageList` to be used
    as if it were a list itself.
    """

    
    def _validateImage(self, atts, images):
        """Returns ``True`` if all objects in the given ``images`` list are
        :class:`Image` objects, ``False`` otherwise.
        """
        return all(map(lambda img: isinstance(img, Image), images))


    images = props.List(validateFunc=_validateImage, allowInvalid=False)
    """A list of :class:`Image` objects. to be displayed"""

    
    def __init__(self, images=None):
        """Create an ImageList object from the given sequence of
        :class:`Image` objects."""
        
        if images is None: images = []
        self.images.extend(images)


    def addImages(self, fromDir=None, addToEnd=True):
        """Convenience method for interactively adding images to this
        :class:`ImageList`.

        See the :func:`fsl.data.imageio.addImages` function.
        """
        return iio.addImages(self, fromDir, addToEnd)


    def find(self, name):
        """Returns the first image with the given name, or ``None`` if
        there is no image with said name.
        """
        for image in self.images:
            if image.name == name:
                return image
        return None
            

    # Wrappers around the images list property, allowing this
    # ImageList object to be used as if it is actually a list.
    def __len__(     self):               return self.images.__len__()
    def __getitem__( self, key):          return self.images.__getitem__(key)
    def __iter__(    self):               return self.images.__iter__()
    def __contains__(self, item):         return self.images.__contains__(item)
    def __setitem__( self, key, val):     return self.images.__setitem__(key,
                                                                         val)
    def __delitem__( self, key):          return self.images.__delitem__(key)
    def index(       self, item):         return self.images.index(item)
    def count(       self, item):         return self.images.count(item)
    def append(      self, item):         return self.images.append(item)
    def extend(      self, iterable):     return self.images.extend(iterable)
    def pop(         self, index=-1):     return self.images.pop(index)
    def move(        self, from_, to):    return self.images.move(from_, to)
    def remove(      self, item):         return self.images.remove(item)
    def insert(      self, index, item):  return self.images.insert(index,
                                                                    item)
    def insertAll(   self, index, items): return self.images.insertAll(index,
                                                                       items) 
