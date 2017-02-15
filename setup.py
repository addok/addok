"Search engine for address. Only address."
import glob
import sys
from codecs import open  # To use a consistent encoding
from os import path

from setuptools import Extension, find_packages, setup

here = path.abspath(path.dirname(__file__))

# Get the long description from the relevant file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


def is_pkg(line):
    return line and not line.startswith(('--', 'git', '#'))


def list_modules(dirname):
    filenames = glob.glob(path.join(dirname, '*.py'))

    module_names = []
    for name in filenames:
        module, ext = path.splitext(path.basename(name))
        if module != '__init__':
            module_names.append(module)

    return module_names


with open('requirements.txt', encoding='utf-8') as reqs:
    install_requires = [l for l in reqs.read().split('\n') if is_pkg(l)]

if sys.platform == 'darwin':
    install_requires.append('gnureadline==6.3.3')

try:
    from Cython.Distutils import build_ext
    CYTHON = True
except ImportError:
    sys.stdout.write('\nNOTE: Cython not installed. Addok will '
                     'still work fine, but may run a bit slower.\n\n')
    CYTHON = False
    cmdclass = {}
    ext_modules = []
else:
    ext_modules = [
        Extension('addok.' + ext, [path.join('addok', ext + '.py')])
        for ext in list_modules(path.join(here, 'addok'))]

    ext_modules.extend([
        Extension('addok.helpers.' + ext,
                  [path.join('addok', 'helpers', ext + '.py')])
        for ext in list_modules(path.join(here, 'addok', 'helpers'))])

    cmdclass = {'build_ext': build_ext}

VERSION = (1, 0, 0, 'rc', 1)

__author__ = 'Yohan Boniface'
__contact__ = "yohan.boniface@data.gouv.fr"
__homepage__ = "https://github.com/addok/addok"
__version__ = ".".join(map(str, VERSION))

setup(
    name='addok',
    version=__version__,
    description=__doc__,
    long_description=long_description,
    url=__homepage__,
    author=__author__,
    author_email=__contact__,
    license='WTFPL',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 4 - Beta',

        'Intended Audience :: Developers',
        'Topic :: Scientific/Engineering :: GIS',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    keywords='address openstreetmap geocoding',
    packages=find_packages(exclude=['tests']),
    install_requires=install_requires,
    extras_require={'test': ['pytest'], 'docs': 'mkdocs'},
    include_package_data=True,
    ext_modules=ext_modules,
    entry_points={
        'console_scripts': ['addok=addok.bin:main'],
        'pytest11': ['addok=addok.pytest'],
    },
    cmdclass=cmdclass,
)
