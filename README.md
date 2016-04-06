fslpy
=====

The `fslpy` project is a [FSL](http://fsl.fmrib.ox.ac.uk/fsl/fslwiki/)
programming library written in Python. It is used by
[FSLeyes](https://git.fmrib.ox.ac.uk/paulmc/fsleyes/).


Documentation
-------------


Take a look at the [Documentation for
developers](http://users.fmrib.ox.ac.uk/~paulmc/fslpy/index.html) if you want
to program with `fslpy`.


Dependencies
------------


`fslpy` depends upon the following libraries:


| Library                                           | Version |
| ------------------------------------------------- | ------- |
| [props](https://git.fmrib.ox.ac.uk/paulmc/props/) | Latest  |
| [numpy](http://www.numpy.org/)                    | 1.8.1   |
| [scipy](http://www.scipy.org/)                    | 0.14.0  |
| [matplotlib](http://matplotlib.org/)              | 1.4.3   |
| [nibabel](http://nipy.org/nibabel/)               | 1.3.0   |
| [six](https://pythonhosted.org/six/)              | 1.10.0  |
| [Sphinx](http://www.sphinx-doc.org/en/stable/)    | 1.3.5   |
| [wxPython](http://wxpython.org/)                  | 3.0.2.0 |

 > Notes:
 >   - Sphinx is only needed for building the documentation.
 > 
 >   - If you are installing `fslpy` manually, don't worry too much about 
 >     having the exact version of each of the packages - just try with 
 >     the latest version, and roll-back if you have problems.
