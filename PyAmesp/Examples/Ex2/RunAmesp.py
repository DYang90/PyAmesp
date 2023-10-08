"""Ex. 2 1,3-Butadiene and Ethylene
    In this example, the structures of 1,3-Butadiene and Ethylene will be
    optimized by using GDIIS optimizer implemented in Gaussian. The M06-2X
    functional with 6-31g(d,p) basis sets will be utilized.
"""
from ase import io
from PyAmesp import Amesp, GaussianExternal
from ase.calculators.gaussian import Gaussian, GaussianOptimizer

label = 'reactant'
atoms = io.read('%s.xyz' % label)
amesp = Amesp(atoms=atoms,
              label=label,
              maxcore=1024, npara=12,
              charge=0, mult=1,
              keywords=['m06-2x', '6-31g**', 'grid5', 'force']
              )
gext = GaussianExternal(label=label, parameters=amesp.parameters)
# Generate gaussian_amesp.py which include the parameters of Amesp.
gext.write_script()
gau = Gaussian(label=label, external='\'python3 gaussian_amesp.py\'')
opt = GaussianOptimizer(atoms, gau)
opt.run(fmax='tight', steps=100, opt='nomicro,gdiis')
