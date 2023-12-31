""" This module defines a ASE interface for AMESP
https://amesp.xyz/

Author
------
J. Zhao
D. Yang
YF. Zhang

Date
----
July 12 2023
"""

import re
from io import StringIO
from copy import deepcopy
import numpy as np
from ase import io, Atoms
from ase.units import Hartree, Bohr
from ase.io.zmatrix import parse_zmatrix
from ase.utils import reader, writer
import os
from ase.calculators.calculator import FileIOCalculator


class Amesp(FileIOCalculator):
    implemented_properties = ['energy', 'forces', 'charges',
                              'dipole', 'magmoms']
    if 'AMESP_COMMAND' in os.environ:
        command = os.environ['AMESP_COMMAND']+'PREFIX.aip PREFIX.aop'
    else:
        command = 'amesp PREFIX.aip PREFIX.aop'

    def __init__(self, restart=None,
                 ignore_bad_restart_file=FileIOCalculator._deprecated,
                 label='amesp', atoms=None, **kwargs):
        """
        Calculator interface to the Amesp.

        Parameters:
        -----------
        label (str) - The name of file.
        atoms (Atoms) – The structure of the molecule.

        Example:
        --------
        ! hf 3-21g
        >method
          eda mayer
        end
        >xyz 0 1
         C    	 0.          0.         0.
         H    	 0.629118   0.629118   0.629118
         H    	-0.629118  -0.629118   0.629118
         H    	 0.629118  -0.629118  -0.629118
         H    	 0.629118   0.629118  -0.629118
        end

        This can be generated by this module by using the
        following settings:

        >>> from ase.build import molecule
        >>> atoms = molecule('CH4')
        >>> from PyAMESP import Amesp
        >>> keywords = ['hf','3-21g']
        >>> method = {'eda':'mayer'}
        >>> calc = Amesp(atoms=atoms, method=method)

        Suppports
        ---------
        Energy, gradients, dipole moments, charge
        and spin populations.

        Todo
        ----
        Orbital energies, keyword verification, point charges, etc.
        """
        FileIOCalculator.__init__(self, restart, ignore_bad_restart_file,
                                  label, atoms, **kwargs)

    def set(self, **kwargs):
        changed_parameters = FileIOCalculator.set(self, **kwargs)
        if changed_parameters:
            self.reset()

    def clean(self):
        for suffix in ['.aip', '.aop', '.mo']:
            try:
                os.remove(os.path.join(self.directory, self.label+suffix))
            except OSError:
                pass

    def write_input(self, atoms, properties=None, system_changes=None):
        FileIOCalculator.write_input(self, atoms, properties, system_changes)
        p = self.parameters
        """ Write *.aip file """
        with open(self.label+'.aip', 'w+') as fd:
            write_aip(fd, atoms, properties=properties, **p)

    def read_results(self):
        """ Read *.aop file and collect data """
        with open(self.label+'.aop') as fd:
            text = fd.read()
            """xyz"""
            element, position = parse_aop_xyz(text)
            nimage = len(element)
            """charge"""
            self.results['charge'] = parse_aop_charge(text, nimage)[-1]
            """spin"""
            self.results['magmoms'] = parse_aop_spin(text, nimage)[-1]
            """dipole"""
            self.results['dipole'] = parse_aop_dipole(text, nimage)[-1]
            """energy"""
            self.results['energy'] = parse_aop_energy(text, nimage)[-1]
            """forces"""
            self.results['forces'] = parse_aop_force(text)


class GaussianExternal:
    def __init__(self, label='amesp', parameters=None):
        """
        Parameters:
        -----------
        label (str) - The name of file.
        parameters (**kwargs) - The paramters of Amesp.

        Examples:
        ---------
        atoms = io.read('C2H6.xyz')
        amesp = Amesp(atoms=atoms,
                      label=label,
                      maxcore=1024, npara=12,
                      charge=0, mult=1,
                      keywords=['pbe0', '6-31g*', 'grid5', 'force']
                      )
        gext = GaussianExternal(label='C2H6', parameters=amesp.parameters)
        gext.write_script()
        gau = Gaussian(label='C2H6', external='\'python3 gaussian_amesp.py\'')
        opt = GaussianOptimizer(atoms, gau)
        opt.run(fmax='tight', steps=100, opt='nomicro,gdiis')
        """
        self.parameters = parameters
        self.label = label
        self.atoms = None

    def write_script(self):
        # generate gaussian_amesp.py as interface
        text = []
        text.append('import sys')
        text.append('from PyAmesp import GaussianExternal')
        text.append('')
        text.append('parameters = %s' % self.parameters)
        text.append(
            'gext = GaussianExternal(label = \'%s\', parameters = parameters)' % self.label)
        text.append('gext.run(sys.argv[2], sys.argv[3])')
        text = '\n'.join(text)
        with open('gaussian_amesp.py', 'w+') as fd:
            fd.write(text)

    def read_EIn(self, ein):
        # read Gau-XXX.EIn
        with open(ein) as fd:
            lines = fd.read().splitlines()
            natoms, nderiv, charge, mult = np.array(lines[0].split(), int)
            self.parameters['charge'] = charge
            self.parameters['mult'] = mult
            xyz_text = np.array([line.split() for line in lines[1:natoms+1]])
            numbers = np.array(xyz_text[:, 0], int)
            positions = np.array(xyz_text[:, 1:4], float)*Bohr
        self.atoms = Atoms(numbers=numbers, positions=positions)

    def write_EOu(self, eou):
        results = self.atoms.calc.results
        eou_text = []
        pattern = ''.join(['%20.12E']*4)
        dipole = results['dipole']/Bohr
        dipole = np.insert(dipole, 0, results['energy']/Hartree)
        eou_text.append(pattern % tuple(dipole))
        pattern = ''.join(['%20.12E']*3)
        forces = results['forces']*Bohr/Hartree*(-1)
        forces = [pattern % tuple(force) for force in forces]
        eou_text += forces
        eou_text = '\n'.join(eou_text)
        with open(eou, 'w+') as fd:
            fd.write(eou_text)

    def run(self, ein, eou):
        self.read_EIn(ein)
        calc = Amesp(atoms=self.atoms, label=self.label, **self.parameters)
        self.atoms.calc = calc
        self.atoms.get_potential_energy()
        self.write_EOu(eou)


def parse_xyz(text):
    pattern = '>xyz\s+\d+\s+\d+'
    pattern += '\s*\n(.*?)\n\s*end'
    xyz_text = re.findall(pattern, text, re.S)
    if len(xyz_text) == 1:
        xyz_text = xyz_text[0]
        natoms = len(xyz_text.split('\n'))
        """ transform into xyz then parse """
        xyz_text = '%d\n\n%s' % (natoms, xyz_text)
    else:
        xyz_text = None
    atoms = io.read(StringIO(xyz_text), format='xyz')
    return atoms


def parse_zmat(text):
    pattern = '>coord\s*\n(.*?)\n\s*end'
    coord = re.findall(pattern, text, re.S)
    if len(coord) == 1:
        coord = coord[0]
        coord = ['='.join(c.split()[:2]) for c in coord.split('\n')]
        coord = '\n'.join(coord)
    else:
        coord = ''
    pattern = '>zmat\s+\d+\s+\d+'
    pattern += '\s*\n(.*?)\n\s*end'
    zmat = re.findall(pattern, text, re.S)
    if len(zmat) == 1:
        zmat = zmat[0]
    else:
        zmat = None
    atoms = parse_zmatrix(zmat, defs=coord)
    return atoms


@reader
def read_aip(fd):
    """
    Read an Amesp input file.

    Usage:
    -------
    >>> with open('CH4.aip', 'r+') as fd
    >>> atoms = read_aip(fd)
    >>> print(atoms)
    Atoms(symbols='CH4', pbc=False)

    Parameters:
    -----------
    fd (file) - A file like object.

    Return:
    atoms (Atoms) – The structure of the molecule.

    """
    text = fd.read()
    if '>xyz' in text:
        atoms = parse_xyz(text)
    elif '>zmat' in text:
        atoms = parse_zmat(text)
    else:
        atoms = None
    return atoms


def parse_aop_xyz(text):
    pattern = 'Current Geometry\(angstroms\):'
    pattern += '\n\s*\n(.*?)\n\s*\n'
    xyz_array = re.findall(pattern, text, re.S)
    element = [np.array([x.split()[0]
                         for x in xyz.split('\n')])
               for xyz in xyz_array]
    position = [np.array([x.split()[1:]
                         for x in xyz.split('\n')], float)
                for xyz in xyz_array]
    return element, position


def parse_aop_charge(text, n):
    pattern = '\w+ charges:\n\s*\n(.*?)\n\s*'
    pattern += 'Sum of \w+ charges'
    charge_array = re.findall(pattern, text, re.S)
    charge_array = [np.array([c.split()[-1]
                             for c in charge.split('\n')], dtype=float)
                    for charge in charge_array]
    charge_array = charge_array[:n+1]
    if len(charge_array) == 0:
        charge_array = [None for i in range(n)]
    return charge_array


def parse_aop_spin(text, n):
    """
    Note: To collect spin populations, the settings

    >>>Amesp(...,ope={'out':2},...)

    should be activated.
    """
    pattern = 'Spin densities:\n\s*\n(.*?)\n\s*\n'
    spin_array = re.findall(pattern, text, re.S)
    spin_array = [np.array([s.split()[-1]
                           for s in spin.split('\n')], dtype=float)
                  for spin in spin_array]
    spin_array = spin_array[:n+1]
    if len(spin_array) == 0:
        spin_array = [None for i in range(n)]
    return spin_array


def parse_aop_dipole(text, n):
    pattern = 'Dipole moment \(.*?\):\n'
    pattern += '\s*X=\s*(.*?)'
    pattern += '\s*Y=\s*(.*?)'
    pattern += '\s*Z=\s*(.*?)'
    pattern += '\s*Tot='
    dipole = re.findall(pattern, text, re.S)
    dipole = [np.array(d, float)*Bohr for d in dipole]
    dipole = dipole[:n+1]
    return dipole


def parse_aop_energy(text, n):
    pattern = 'ETot =\s*(.*?)\s*Ekin'
    energy = re.findall(pattern, text)
    energy = np.array(energy, float)*Hartree
    energy = energy[:n+1]
    return energy


def parse_aop_gradient(text, n):
    pattern = 'Cartesian Gradient \(.*?\):\n'
    pattern += '\s*x\s*y\s*z\n(.*?)\n\s*\n'
    force_data = re.findall(pattern, text, re.S)
    if len(force_data) > 0:
        force_data = [np.array([f.split()[1:]
                               for f in force.split('\n')], float)*Hartree/Bohr*(-1)
                      for force in force_data]
        force_data = force_data[:n+1]
    else:
        force_data = [None for i in range(n)]
    return force_data


def parse_aop_force(text):
    pattern = 'Cartesian Force \(.*?\):\n'
    pattern += '\s*x\s*y\s*z\n(.*?)\n\s*\n'
    force_data = re.findall(pattern, text, re.S)
    if len(force_data) > 0:
        force = force_data[0]
        force_data = np.array([f.split()[1:]
                              for f in force.split('\n')], float)*Hartree/Bohr
    else:
        force_data = None
    return force_data


@reader
def iread_aop(fd):
    """
    Iterator for reading Atoms objects from file.

    Usage:
    ------
    >>> fd = open('C6H6.aop')
    >>> images = list(iread_aop(fd))

    Parameters:
    -----------
    fd(file) - A file like object.

    Return:
    Iterator of Atoms objects.
    """
    text = fd.read()
    """xyz"""
    element, position = parse_aop_xyz(text)
    nimage = len(element)
    """charge"""
    charge = parse_aop_charge(text, nimage)
    """spin"""
    magmom = parse_aop_spin(text, nimage)
    """dipole"""
    dipole = parse_aop_dipole(text, nimage)
    """energy"""
    energy = parse_aop_energy(text, nimage)
    """forces"""
    force = parse_aop_gradient(text, nimage)
    images = []
    for i in range(nimage):
        atoms = Atoms(element[i], position[i])
        results = {}
        results['energy'] = energy[i]
        results['forces'] = force[i]
        results['dipole'] = dipole[i]
        results['charges'] = charge[i]
        results['magmoms'] = magmom[i]
        amesp = Amesp(atoms=atoms)
        amesp.results = results
        atoms.calc = amesp
        images.append(atoms)
    """ Transform list into generator """
    images = (image for image in images)
    return images


def read_aop(fd, index=-1):
    """
    Read an Amesp output file.

    Usage:
    ------
    >>> fd = open('C6H6.aop')
    >>> atoms = read_aop(fd)

    Parameters:
    -----------
    fd (file) - A file like object.
    index (slice) - The index of configurations to extract.

    Return:
    -------
    atoms (Atoms) – The structure of the molecule.
    """
    atoms = list(iread_aop(fd))[index]
    return atoms


def write_xyz(atoms, kw):
    if 'charge' in kw:
        charge = kw.pop('charge')
    else:
        charge = atoms.get_initial_charges().sum()
    if 'mult' in kw:
        mult = kw.pop('mult')
    else:
        mult = atoms.get_initial_magnetic_moments().sum()
        mult = abs(int(round(mult)))+1
    fd = StringIO()
    io.write(fd, atoms, format='xyz')
    fd.seek(0)
    text = fd.readlines()[2:]
    text = ['>xyz %d %d\n' % (charge, mult)]+text+['end']
    text = ''.join(text)
    return text


def write_job(kw):
    text = []
    if 'npara' in kw:
        npara = kw.pop('npara')
        text.append('%% npara %d' % npara)
    if 'maxcore' in kw:
        maxcore = kw.get('maxcore')
        text.append('%% maxcore %d' % maxcore)
    text = '\n'.join(text)
    return text


def write_keywords(properties, kw):
    if 'keywords' in kw:
        keywords = kw.pop('keywords')
    else:
        keywords = ['pbe0', 'def2-svp']
    text = ['!']
    text += keywords
    text = ' '.join(text)
    return text


def kv_fmt(k, v):
    """ parse key-value pair in parameter blocks"""
    if isinstance(v, str):
        kv = ' %s %s' % (k, v)
    elif isinstance(v, float):
        kv = ' %s %f' % (k, v)
    elif isinstance(v, bool):
        vv = {False: 'off', True: 'on'}
        kv = ' %s %s' % (k, vv[v])
    elif isinstance(v, int):
        kv = ' %s %d' % (k, v)
    else:
        kv = None
    return kv


def write_dict(kw):
    block = {}
    for k0, v0 in kw.items():
        if isinstance(v0, dict):
            kv = {}
            for k1, v1 in v0.items():
                if isinstance(v1, (str, bool, int, float)):
                    kv[k1] = v1
            if len(kv) > 0:
                block[k0] = kv
    if len(block) > 0:
        text = []
        for k0, v0 in block.items():
            text.append('>%s' % k0)
            kv_text = []
            for k1, v1 in v0.items():
                kv = kv_fmt(k1, v1)
                if kv is not None:
                    kv_text.append(kv)
            kv_text = '\n'.join(kv_text)
            text.append(kv_text)
            text.append('end')
        text = '\n'.join(text)
    else:
        text = ''
    return text


@writer
def write_aip(fd, atoms, properties=None, **kw):
    """
    Generate an Amesp input file.

    Parameters:
    -----------
    fd (file) - A file like object.
    atoms – Structure defined in the input file.
    properties (list) – Properties to calculate

    Usage:
    ------
    >>> from ase import io
    >>> atoms=io.read('NH3.gjf')
    >>> with open('NH3.aip',atoms):
                    write_aip(fd,atoms)
    """
    if not isinstance(atoms, Atoms):
        if len(atoms) > 1:
            atoms = atoms[-1]
    kw = deepcopy(kw)
    text = []
    """job control"""
    text.append(write_job(kw))
    """keywords"""
    text.append(write_keywords(properties, kw))
    """block"""
    text.append(write_dict(kw))
    """molecular structure"""
    text.append(write_xyz(atoms, kw))
    """blank filter"""
    text = [t for t in text if len(t) > 0]
    text = '\n'.join(text)
    fd.write(text)
