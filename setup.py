# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

about = {}
with open(path.join(here, 'pysnc', '__version__.py'), 'r', 'utf-8') as f:
    exec(f.read(), about)

setup(
    name=about['__title__'],
    version=about['__version__'],
    description='Python SNC (REST) API',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/ServiceNow/PySNC',
    author='Matthew Gill',
    author_email='matthew.gill@servicenow.com',
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Operating System :: OS Independent',
    ],
    keywords='',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    test_suite='nose.collector',
    tests_require=['nose', 'PyYAML>=3.12', 'requests-oauthlib>=1.2.0'],
    install_requires=['requests>=2.18.1', 'six>=1.10.0'],
    extras_require= {
        'oauth': ['requests-oauthlib>=1.2.0']
    }
)
