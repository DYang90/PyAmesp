import sys
from setuptools import setup, find_packages

python_min_version = (3, 6)
python_requires = '>=' + '.'.join(str(num) for num in python_min_version)

if sys.version_info < python_min_version:
    raise SystemExit('Python 3.6 or later is required!')

install_requires = [
    'numpy>=1.11.3',
    'ase>=3.20.0'
]

setup(
    name='PyAmesp',
    version='1.0',
    url='https://www.amesp.xyz',
    maintainer='J. Zhao, D. Yang, YF. Zhang',
    maintainer_email='',
    license='LGPLv2.1+',
    platforms=['unix'],
    packages=find_packages(),
    python_requires=python_requires,
    install_requires=install_requires,
    classifiers=[
            'License :: OSI Approved :: '
        'GNU Lesser General Public License v2 or later (LGPLv2+)',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3'
    ]
)
