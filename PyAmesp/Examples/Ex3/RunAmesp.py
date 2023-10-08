"""Ex. 3 Diels-Alder Reaction
    In this example, the transition path of Diels-Alder reaction will be
    searched by CI-NEB method with LBFGS optimizer implemented in ASE. The
    initial guess for the path will be interpolated using IDPP method, the
    M06-2X functional with 6-31g(d,p) basis sets will be utilized.
"""
from ase import io
from PyAmesp import Amesp
from ase.optimize import *
from ase.neb import NEB

label = 'neb'
ini = io.read('reactant.traj')
fin = io.read('product.traj')
images = [ini.copy() for i in range(6)]
for i, img in enumerate(images):
    amesp = Amesp(atoms=img,
                  label=label,
                  maxcore=1024, npara=12,
                  charge=0, mult=1,
                  keywords=['m06-2x', '6-31g**', 'grid5', 'force']
                  )
    img.calc = amesp
images[0] = ini
images[-1] = fin
neb = NEB(images, climb=True)
neb.interpolate(method='idpp')
dyn = LBFGS(neb, trajectory='%s.traj' % label)
dyn.run(fmax=0.02)
images[0] = ini
images[-1] = fin
io.write('%s.json' % label, images)
