#!/usr/bin/env python
#
# settings.py - Persistent application settings.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides functions for storing and retrieving persistent
configuration settings and data files.

The :func:`initialise` function must be called to initialise the module. Then,
the following functions can be called at the module-level:

.. autosummary::
   :nosignatures:

   Settings.read
   Settings.write
   Settings.delete
   Settings.readFile
   Settings.writeFile
   Settings.deleteFile
   Settings.clear

These functions will have no effect before :func:`initialise` is called.

Two types of configuration data are available:

  - Key-value pairs - access these via the ``read``, ``write`` and ``delete``
    functions. These are stored in a single file, via ``pickle``. Anything
    that can be pickled can be stored.

  - Separate files, either text or binary. Access these via the ``readFile``,
    ``writeFile`, and ``deleteFile` functions.

Both of the above data types will be stored in a configuration directory.
The location of this directory differs from platform to platform, but is
likely to be either  `~/.fslpy/` or `~/.config/fslpy/`.
"""


from __future__ import absolute_import

import            os
import os.path as op
import            sys
import            atexit
import            shutil
import            pickle
import            logging
import            tempfile
import            platform


log = logging.getLogger(__name__)


_CONFIG_ID = 'fslpy'
"""The default configuration identifier, used as the directory name for 
storing configuration files.
"""


def initialise(*args, **kwargs):
    """Initialise the ``settings`` module. This function creates a
    :class:`Settings` instance, and enables the module-level
    functions. All settings are passed through to :meth:`Settings.__init__`.
    """
    
    mod = sys.modules[__name__]

    settings       = Settings(*args, **kwargs)
    mod.settings   = settings
    mod.read       = settings.read
    mod.write      = settings.write
    mod.delete     = settings.delete
    mod.readFile   = settings.readFile
    mod.writeFile  = settings.writeFile
    mod.deleteFile = settings.deleteFile
    mod.clear      = settings.clear


# These are all overwritten by
# the initialise function.
def read(name, default=None):
    return default
def write(*args, **kwargs):
    pass
def delete(*args, **kwargs):
    pass
def readFile(*args, **kwargs):
    pass
def writeFile(*args, **kwargs):
    pass
def deleteFile(*args, **kwargs):
    pass
def clear(*args, **kwarg):
    pass


class Settings(object):
    """The ``Settings`` class contains all of the logic provided by the
    ``settings`` module.  It is not meant to be instantiated directly
    (although you may do so if you wish).

    .. autosummary::
       :nosignatures:

        read
        write
        delete
        readFile
        writeFile
        deleteFile
        clear
    """


    def __init__(self, cfgid=_CONFIG_ID, cfgdir=None, writeOnExit=True):
        """Create a ``Settings`` instance.

        :arg cfgid:       Configuration ID, used as the name of the
                          configuration directory.

        :arg cfgdir:      Store configuration settings in this directory, 
                          instead of the default.

        :arg writeOnExit: If ``True`` (the default), an ``atexit`` function
                          is registered, which calls :meth:`writeConfigFile`.
        """

        if cfgdir is None:
            cfgdir = self.__getConfigDir(cfgid)

        self.__configID  = cfgid
        self.__configDir = cfgdir
        self.__config    = self.__readConfigFile()

        if writeOnExit:
            atexit.register(self.writeConfigFile)


    @property
    def configID(self):
        """Returns the configuration identifier. """
        return self.__configID


    @property
    def configDir(self):
        """Returns the location of the configuration directory. """
        return self.__configDir


    def read(self, name, default=None):
        """Reads a setting with the given ``name``, return ``default`` if
        there is no setting called ``name``.
        """ 

        log.debug('Reading {}/{}'.format(self.__configID, name))
        return self.__config.get(name, default)


    def write(self, name, value):
        """Writes the given ``value`` to the given file ``path``. """

        log.debug('Writing {}/{}: {}'.format(self.__configID, name, value))
        self.__config[name] = value


    def delete(self, name):
        """Delete the setting with the given ``name``. """

        log.debug('Deleting {}/{}'.format(self.__configID, name))
        self.__config.pop(name, None)


    def readFile(self, path, mode='t'):
        """Reads and returns the contents of the given file ``path``. 
        Returns ``None`` if the path does not exist.
        """

        mode = 'r' + mode
        path = self.__fixPath(path)
        path = op.join(self.__configDir, path)

        if op.exists(path):
            with open(path, mode) as f:
                return f.read()
        else:
            return None


    def writeFile(self, path, value, mode='t'):
        """Writes the given ``value`` to the given file ``path``. """

        mode    = 'w' + mode
        path = self.__fixPath(path)
        path    = op.join(self.__configDir, path)
        pathdir = op.dirname(path)

        if not op.exists(pathdir):
            os.makedirs(pathdir)

        with open(path, mode) as f:
            f.write(value)


    def deleteFile(self, path):
        """Deletes the given file ``path``. """

        path = self.__fixPath(path)
        path = op.join(self.__configDir, path)

        if op.exists(path):
            os.remove(path)


    def clear(self):
        """Delete all configuration settings and files. """

        log.debug('Clearing all settings in {}'.format(self.__configID))

        self.__config = {}

        for path in os.listdir(self.__configDir):
            path = op.join(self.__configDir, path)
            if op.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)


    def __fixPath(self, path):
        """Ensures that the given path (passed into :meth:`readFile`,
        :meth:`writeFile`,  or :meth:`deleteFile`) is cross-platform
        compatible.
        """
        return op.join(*path.split('/'))


    def __getConfigDir(self, cid):
        """Returns a directory in which configuration files can be stored.

        .. note:: If, for whatever reason, a configuration directory could not
                  be located or created, a temporary directory will be used.
                  This means that all settings read during this session will
                  be lost on exit.
        """

        cfgdir  = None
        homedir = op.expanduser('~')

        # On linux, if $XDG_CONFIG_HOME is set, use $XDG_CONFIG_HOME/fslpy/ 
        # Otherwise, use $HOME/.config/fslpy/
        #
        # https://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html
        if platform.system().lower().startswith('linux'):

            basedir = os.environ.get('XDG_CONFIG_HOME')
            if basedir is None:
                basedir = op.join(homedir, '.config')

            cfgdir = op.join(basedir, cid)

        # On all other platforms, use $HOME/.fslpy/
        else:
            cfgdir = op.join(homedir, '.{}'.format(cid))

        # Try and create the config directory
        # tree if it does not exist
        if not op.exists(cfgdir):
            try:
                os.makedirs(cfgdir)
            except:
                log.warning(
                    'Unable to create {} configuration '
                    'directory: {}'.format(cid, cfgdir),
                    exc_info=True)
                cfgdir = None

        # If dir creation failed, use a temporary 
        # directory, and delete it on exit
        if cfgdir is None:
            cfgdir = tempfile.mkdtemp()
            atexit.register(shutil.rmtree, cfgdir, ignore_errors=True)

        log.debug('{} configuration directory: {}'.format(cid, cfgdir))

        return cfgdir


    def __readConfigFile(self):
        """Called by :meth:`__init__`. Reads any settings that were stored
        in a file, and returns them in a dictionary.
        """

        configFile = op.join(self.__configDir, 'config.pkl')

        log.debug('Reading {} configuration from: {}'.format(
            self.__configID, configFile))
        
        try:
            with open(configFile, 'rb') as f:
                return pickle.load(f)
        except:
            log.warning('Unable to load stored {} configuration file '
                        '{}'.format(self.__configID, configFile),
                        exc_info=True)
            return {}


    def writeConfigFile(self):
        """Writes all settings to a file.""" 

        config     = self.__config
        configFile = op.join(self.__configDir, 'config.pkl')

        log.debug('Writing {} configuration to: {}'.format(
            self.__configID, configFile)) 
        
        try:
            with open(configFile, 'wb') as f:
                pickle.dump(config, f)
        except:
            log.warning('Unable to save {} configuration file '
                        '{}'.format(self.__configID, configFile),
                        exc_info=True)
