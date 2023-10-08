"""Ex. 1 Cyclohexene
    In this example, the structure of cyclohexene will be optimized by using
    BFGSLineSearch optimizer implemented in ASE. The M06-2X functional with
    6-31g(d,p) basis sets will be utilized.
"""
from ase import io
from PyAmesp import Amesp
from ase.optimize import BFGSLineSearch

label = 'product'
atoms = io.read('%s.xyz' % label)
amesp = Amesp(atoms=atoms,
              label=label,
              maxcore=1024, npara=12,
              charge=0, mult=1,
              keywords=['m06-2x', '6-31g**', 'grid5', 'force']
              )
atoms.calc = amesp
dyn = BFGSLineSearch(atoms)
traj = io.Trajectory('%s.traj' % label, 'w', atoms)
dyn.attach(traj)
dyn.run(fmax=0.02)
