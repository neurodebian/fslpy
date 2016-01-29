#!/usr/bin/env python
#
# dataseries.py - The DataSeries class.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides the :class:`DataSeries` class, the base class for
classes used by :class:`.PlotPanel` views for plotting data.
"""

import logging

import props


log = logging.getLogger(__name__)


class DataSeries(props.HasProperties):
    """A ``DataSeries`` instance encapsulates some data to be plotted by
    a :class:`PlotPanel`, with the data extracted from an overlay in the
    :class:`.OverlayList`. 

    Sub-class implementations must accept an overlay object, pass this
    overlay to the ``DataSeries`` constructor, and override the
    :meth:`getData` method. The overlay is accessible as an instance
    attribute, confusingly called ``overlay``.

    Each``DataSeries`` instance is plotted as a line, with the line
    style defined by properties on the ``DataSeries`` instance,
    such as :attr:`colour`, :attr:`lineWidth` etc.
    """

    colour = props.Colour()
    """Line colour. """

    
    alpha = props.Real(minval=0.0, maxval=1.0, default=1.0, clamped=True)
    """Line transparency."""

    
    label = props.String()
    """Line label (used in the plot legend)."""

    
    lineWidth = props.Choice((0.5, 1, 2, 3, 4, 5))
    """Line width. """

    
    lineStyle = props.Choice(('-', '--', '-.', ':'))
    """Line style. """

    
    def __init__(self, overlay):
        """Create a ``DataSeries``.

        :arg overlay: The overlay from which the data to be plotted is
                      retrieved. 
        """
        
        self.overlay = overlay
        self.setData([], [])

        log.memory('{}.init ({})'.format(type(self).__name__, id(self)))

                   
    def __del__(self):
        """Prints a log message. """
        if log:
            log.memory('{}.del ({})'.format(type(self).__name__, id(self)))


    def destroy(self):
        """This method must be called when this ``DataSeries`` instance is no
        longer needed. This implementation does nothing, but it should be
        overridden by sub-classes which need to perform any clean-up
        operations.
        """
        pass


    def setData(self, xdata, ydata):
        """Set the data to be plotted. This method is irrelevant if a
        ``DataSeries`` sub-class has overridden :meth:`getData`.
        """
        self.__xdata = xdata
        self.__ydata = ydata 


    def getData(self):
        """This method should be overridden by sub-classes. It must return
        the data to be plotted, as a tuple of the form:
        
            ``(xdata, ydata)``

        where ``xdata`` and ``ydata`` are sequences containing the x/y data
        to be plotted.

        The default implementation returns the data that has been set via the
        :meth:`setData` method.
        """
        return self.__xdata, self.__ydata
