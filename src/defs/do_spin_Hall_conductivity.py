# 
# PAOFLOW
#
# Utility to construct and operate on Hamiltonians from the Projections of DFT wfc on Atomic Orbital bases (PAO)
#
# Copyright (C) 2016-2018 ERMES group (http://ermes.unt.edu, mbn@unt.edu)
#
# Reference:
# M. Buongiorno Nardelli, F. T. Cerasoli, M. Costa, S Curtarolo,R. De Gennaro, M. Fornari, L. Liyanage, A. Supka and H. Wang,
# PAOFLOW: A utility to construct and operate on ab initio Hamiltonians from the Projections of electronic wavefunctions on
# Atomic Orbital bases, including characterization of topological materials, Comp. Mat. Sci. vol. 143, 462 (2018).
#
# This file is distributed under the terms of the
# GNU General Public License. See the file `License'
# in the root directory of the present distribution,
# or http://www.gnu.org/copyleft/gpl.txt .
#

import numpy as np
import cmath
from math import cosh
import sys, time
import scipy.integrate

from mpi4py import MPI
from mpi4py.MPI import ANY_SOURCE
from load_balancing import load_balancing
from communication import scatter_array

from constants import *
from smearing import *

# initialize parallel execution
comm=MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

def do_spin_Hall_conductivity(E_k,jksp,pksp,temp,ispin,npool,ipol,jpol,shift,deltak,deltak2,smearing):
    # Compute the optical conductivity tensor sigma_xy(ene)

    emin = 0.0
    emax = shift
    de = (emax-emin)/500
    ene = np.arange(emin,emax,de,dtype=float)

    nktot,_,nawf,_,nspin = pksp.shape
    nk_tot = np.array([nktot],dtype=int)
    nktot = np.zeros((1),dtype=int)
    comm.Reduce(nk_tot,nktot)

    if rank==0:
        sigxy = np.zeros((ene.size),dtype=complex)
    else: sigxy = None

    sigxy_aux = np.zeros((ene.size),dtype=complex)

    sigxy_aux = smear_sigma_loop(ene,E_k,jksp,pksp,nawf,temp,ispin,ipol,jpol,smearing,deltak,deltak2)
                
    comm.Reduce(sigxy_aux,sigxy,op=MPI.SUM)

    comm.Barrier()

    if rank==0:
        sigxy /= float(nktot)
        return(ene,sigxy)
    else: return None,None


def smear_sigma_loop(ene,E_k,jksp,pksp,nawf,temp,ispin,ipol,jpol,smearing,deltak,deltak2):

    sigxy = np.zeros((ene.size),dtype=complex)
    f_nm = np.zeros((pksp.shape[0],nawf,nawf),dtype=float)
    E_diff_nm = np.zeros((pksp.shape[0],nawf,nawf),dtype=float)
    delta = 0.05
    Ef = 0.0
    #to avoid divide by zero error
    eps=1.0e-16


    if smearing == None:
        fn = 1.0/(np.exp(E_k[:,:,ispin]/temp)+1)
    elif smearing == 'gauss':
        fn = intgaussian(E_k[:,:,0],Ef,deltak[:,:,0])
    elif smearing == 'm-p':
        fn = intmetpax(E_k[:,:,0],Ef,deltak[:,:,0]) 

    # Collapsing the sum over k points
    for n in range(nawf):
        for m in range(nawf):
            if m != n:
                E_diff_nm[:,n,m] = (E_k[:,n,ispin]-E_k[:,m,ispin])**2
                f_nm[:,n,m]      = (fn[:,n] - fn[:,m])*np.imag(jksp[:,jpol,n,m,0]*pksp[:,ipol,m,n,0])

    fn = None

    for e in range(ene.size):
        if smearing!=None:
            sigxy[e] = np.sum(1.0/(E_diff_nm[:,:,:]-(ene[e]+1.0j*deltak2[:,:,:,ispin])**2+eps)*f_nm[:,:,:])
        else:
            sigxy[e] = np.sum(1.0/(E_diff_nm[:,:,:]-(ene[e]+1.0j*delta)**2+eps)*f_nm[:,:,:])
                                                                                 
    F_nm = None
    E_diff_nm = None
                    
    return(np.nan_to_num(sigxy))
