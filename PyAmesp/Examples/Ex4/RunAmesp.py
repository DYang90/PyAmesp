"""Ex. 4 Diels-Alder Reaction
    In this example, the transition path of Diels-Alder reaction will be
    searched by CI-NEB method with LBFGS optimizer implemented in ASE. The
    path will be optimized until the maximal force on each atom is less than
    0.5 eV/Ang. Then, the dimer method will be utilized to refine the structure
    of the transition state. The initial direction along the dimer is set to
    the vector between two higher configurations in the CI-NEB results. The
    M06-2X functional with 6-31g(d,p) basis sets will be utilized.
"""
from ase import io
from PyAmesp import Amesp
from ase.dimer import DimerControl, MinModeAtoms, MinModeTranslate

label = 'dimer'
traj = list(io.iread('neb.json'))
atoms = traj[3].copy()
amesp = Amesp(atoms=atoms,
              label=label,
              maxcore=1024, npara=12,
              charge=0, mult=1,
              keywords=['m06-2x', '6-31g**', 'grid5', 'force']
              )
atoms.calc = amesp
displacement_vector = traj[2].positions-traj[3].positions
d_control = DimerControl(initial_eigenmode_method='displacement',
                         displacement_method='vector')
d_atoms = MinModeAtoms(atoms, d_control)
d_atoms.displace(displacement_vector=displacement_vector)
dyn = MinModeTranslate(d_atoms, trajectory='%s.traj' % label)
dyn.run(fmax=0.02)
