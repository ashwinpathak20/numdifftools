"""
Created on 28. aug. 2015

@author: pab
"""
from __future__ import division, print_function
import numpy as np
from scipy import linalg
from scipy.ndimage.filters import convolve1d
import warnings
EPS = np.finfo(float).eps
_EPS = EPS
_TINY = np.finfo(float).tiny


def convolve(sequence, rule, **kwds):
    """Wrapper around scipy.ndimage.convolve1d that allows complex input."""
    if np.iscomplexobj(sequence):
        return (convolve1d(sequence.real, rule, **kwds) + 1j *
                convolve1d(sequence.imag, rule, **kwds))
    return convolve1d(sequence, rule, **kwds)


class Dea(object):
    """
    LIMEXP  is the maximum number of elements the
    epsilon table data can contain. The epsilon table
    is stored in the first (LIMEXP+2) entries of EPSTAB.


    LIST OF MAJOR VARIABLES
    -----------------------
    E0,E1,E2,E3 - DOUBLE PRECISION
                  The 4 elements on which the computation of
                  a new element in the epsilon table is based.
    NRES   - INTEGER
             Number of extrapolation results actually
             generated by the epsilon algorithm in prior
             calls to the routine.
    NEWELM - INTEGER
             Number of elements to be computed in the
             new diagonal of the epsilon table. The
             condensed epsilon table is computed. Only
             those elements needed for the computation of
             the next diagonal are preserved.
    RES    - DOUBLE PREISION
             New element in the new diagonal of the
             epsilon table.
    ERROR  - DOUBLE PRECISION
             An estimate of the absolute error of RES.
             Routine decides whether RESULT=RES or
             RESULT=SVALUE by comparing ERROR with
             ABSERR from the previous call.
    RES3LA - DOUBLE PREISION
             Vector of DIMENSION 3 containing at most
             the last 3 results.
    """
    def __init__(self, limexp=3):
        self.limexp = limexp
        self.ABSERR = 10.
        self._n = 0
        self._nres = 0

    @property
    def limexp(self):
        return self._limexp

    @limexp.setter
    def limexp(self, limexp):
        n = 2 * (limexp // 2) + 1
        if (n < 3):
            raise ValueError('LIMEXP IS LESS THAN 3')
        self.epstab = np.zeros(n+5)
        self._limexp = n

    @staticmethod
    def _compute_error(RES3LA, NRES, RES):
        fact = [6.0, 2.0, 1.0][min(NRES-1, 2)]
        error = fact * np.abs(RES - RES3LA[:NRES]).sum()
        return error

    @staticmethod
    def _shift_table(EPSTAB, N, NEWELM, old_N):
        i_0 = old_N % 2  # 1 if ((old_N // 2) * 2 == old_N - 1) else 0
        i_n = 2 * NEWELM + 2
        EPSTAB[i_0:i_n:2] = EPSTAB[i_0 + 2:i_n + 2:2]

        if (old_N != N):
            i_n = old_N - N
            EPSTAB[:N + 1] = EPSTAB[i_n:i_n + N + 1]
        return EPSTAB

    @staticmethod
    def _update_RES3LA(RES3LA, RESULT, NRES):
        if NRES > 2:
            RES3LA[:2] = RES3LA[1:]
            RES3LA[2] = RESULT
        else:
            RES3LA[NRES] = RESULT

    def _dea(self, EPSTAB, N):
        NRES = self._nres
        RES3LA = EPSTAB[-3:]
        ABSERR = self.ABSERR
        EPSTAB[N + 2] = EPSTAB[N]
        NEWELM = N // 2
        old_N = N
        K1 = N
        for I in range(NEWELM):
            E0, E1, E2 = EPSTAB[K1 - 2], EPSTAB[K1 - 1], EPSTAB[K1 + 2]
            RES = E2
            DELTA2, DELTA3 = E2 - E1, E1 - E0
            ERR2, ERR3 = abs(DELTA2), abs(DELTA3)
            TOL2 = max(abs(E2), abs(E1)) * _EPS
            TOL3 = max(abs(E1), abs(E0)) * _EPS
            all_converged = (ERR2 <= TOL2 and ERR3 <= TOL3)
            if all_converged:
                ABSERR = ERR2 + ERR3
                RESULT = RES
                break

            if (I == 0):
                any_converged = (ERR2 <= TOL2 or ERR3 <= TOL3)
                if not any_converged:
                    SS = 1.0 / DELTA2 - 1.0 / DELTA3
            else:
                E3 = EPSTAB[K1]
                DELTA1 = E1 - E3
                ERR1 = abs(DELTA1)
                TOL1 = max(abs(E1), abs(E3)) * _EPS
                any_converged = (ERR1 <= TOL1 or ERR2 <= TOL2 or ERR3 <= TOL3)
                if not any_converged:
                    SS = 1.0 / DELTA1 + 1.0 / DELTA2 - 1.0 / DELTA3

            EPSTAB[K1] = E1
            if (any_converged or abs(SS * E1) <= 1e-04):
                N = 2 * I
                if (NRES == 0):
                    ABSERR = ERR2 + ERR3
                    RESULT = RES
                else:
                    RESULT = RES3LA[min(NRES-1, 2)]
                break

            RES = E1 + 1.0 / SS
            EPSTAB[K1] = RES
            K1 = K1 - 2
            if (NRES == 0):
                ABSERR = ERR2 + abs(RES - E2) + ERR3
                RESULT = RES
                continue
            ERROR = self._compute_error(RES3LA, NRES, RES)

            if (ERROR > 10.0 * ABSERR):
                continue
            ABSERR = ERROR
            RESULT = RES
#        else:
#            pass
#            ERROR = self._compute_error(RES3LA, NRES, RES)
            # RESULT = RES

        # 50
        if (N == self.limexp - 1):
            N = 2 * (self.limexp // 2) - 1
        EPSTAB = self._shift_table(EPSTAB, N, NEWELM, old_N)
        self._update_RES3LA(RES3LA, RESULT, NRES)

        ABSERR = max(ABSERR, 10.0*_EPS * abs(RESULT))

        self._nres += 1
        return RESULT, ABSERR, N

    def __call__(self, SVALUE):

        EPSTAB = self.epstab

        RESULT = SVALUE
        N = self._n

        EPSTAB[N] = SVALUE
        if (N == 0):
            ABSERR = abs(RESULT)
        elif (N == 1):
            ABSERR = 6.0 * abs(RESULT - EPSTAB[0])
        else:
            RESULT, ABSERR, N = self._dea(EPSTAB, N)
        N += 1
        self._n = N

        self.ABSERR = ABSERR
        return RESULT, ABSERR


class EpsAlg(object):
    """
    This implementaion is from [1]_

    Reference
    ---------
    ..  [1] E. J. Weniger (1989)
            "Nonlinear sequence transformations for the acceleration of
            convergence and the summation of divergent series"
            Computer Physics Reports Vol. 10, 189 - 371
            http://arxiv.org/abs/math/0306302v1
    """
    def __init__(self, limexp=3):
        self.limexp = 2 * (limexp // 2) + 1
        self.epstab = np.zeros(limexp+5)
        self.ABSERR = 10.
        self._n = 0
        self._nres = 0
        if (limexp < 3):
            raise ValueError('LIMEXP IS LESS THAN 3')

    def __call__(self, SOFN):
        N = self._n
        E = self.epstab
        E[N] = SOFN
        if (N == 0):
            ESTLIM = SOFN
        else:
            AUX2 = 0.0
            for J in range(N, 0, -1):
                AUX1 = AUX2
                AUX2 = E[J-1]
                DIFF = E[J] - AUX2
                if (np.abs(DIFF) <= 1e-60):
                    E[J-1] = 1.0e+60
                else:
                    E[J-1] = AUX1 + 1.0/DIFF
            ESTLIM = E[np.mod(N, 2)]
            if N > self.limexp - 1:
                raise ValueError("Eps table to small!")

        N += 1
        self._n = N
        return ESTLIM


def epsalg_demo():
    def linfun(i):
        return np.linspace(0, np.pi/2., 2**i+1)
    dea = EpsAlg(limexp=15)
    print('NO. PANELS      TRAP. APPROX          APPROX W/EA           ABSERR')
    txt = '{0:5d} {1:20.8f}  {2:20.8f}  {3:20.8f}'
    for k in np.arange(10):
        x = linfun(k)
        val = np.trapz(np.sin(x), x)
        vale = dea(val)
        err = np.abs(1.0-vale)
        print(txt.format(len(x)-1, val, vale, err))


def dea_demo():
    def linfun(i):
        return np.linspace(0, np.pi/2., 2**i+1)
    dea = Dea(limexp=6)
    print('NO. PANELS      TRAP. APPROX          APPROX W/EA           ABSERR')
    txt = '{0:5d} {1:20.8f}  {2:20.8f}  {3:20.8f}'
    for k in np.arange(12):
        x = linfun(k)
        val = np.trapz(np.sin(x), x)
        vale, err = dea(val)
        print(txt.format(len(x)-1, val, vale, err))


def dea3(v0, v1, v2, symmetric=False):
    """
    Extrapolate a slowly convergent sequence

    Parameters
    ----------
    v0, v1, v2 : array-like
        3 values of a convergent sequence to extrapolate

    Returns
    -------
    result : array-like
        extrapolated value
    abserr : array-like
        absolute error estimate

    Description
    -----------
    DEA3 attempts to extrapolate nonlinearly to a better estimate
    of the sequence's limiting value, thus improving the rate of
    convergence. The routine is based on the epsilon algorithm of
    P. Wynn, see [1]_.

     Example
     -------
     # integrate sin(x) from 0 to pi/2

     >>> import numpy as np
     >>> import numdifftools as nd
     >>> Ei= np.zeros(3)
     >>> linfun = lambda i : np.linspace(0, np.pi/2., 2**(i+5)+1)
     >>> for k in np.arange(3):
     ...    x = linfun(k)
     ...    Ei[k] = np.trapz(np.sin(x),x)
     >>> [En, err] = nd.dea3(Ei[0], Ei[1], Ei[2])
     >>> truErr = Ei-1.
     >>> (truErr, err, En)
     (array([ -2.00805680e-04,  -5.01999079e-05,  -1.25498825e-05]),
     array([ 0.00020081]), array([ 1.]))

     See also
     --------
     dea

     Reference
     ---------
     .. [1] C. Brezinski and M. Redivo Zaglia (1991)
            "Extrapolation Methods. Theory and Practice", North-Holland.

    ..  [2] C. Brezinski (1977)
            "Acceleration de la convergence en analyse numerique",
            "Lecture Notes in Math.", vol. 584,
            Springer-Verlag, New York, 1977.

    ..  [3] E. J. Weniger (1989)
            "Nonlinear sequence transformations for the acceleration of
            convergence and the summation of divergent series"
            Computer Physics Reports Vol. 10, 189 - 371
            http://arxiv.org/abs/math/0306302v1
    """
    E0, E1, E2 = np.atleast_1d(v0, v1, v2)
    abs, max = np.abs, np.maximum  # @ReservedAssignment
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # ignore division by zero and overflow
        delta2, delta1 = E2 - E1, E1 - E0
        err2, err1 = abs(delta2), abs(delta1)
        tol2, tol1 = max(abs(E2), abs(E1)) * _EPS, max(abs(E1), abs(E0)) * _EPS
        delta1[err1 < _TINY] = _TINY
        delta2[err2 < _TINY] = _TINY  # avoid division by zero and overflow
        ss = 1.0 / delta2 - 1.0 / delta1 + _TINY
        smalle2 = (abs(ss * E1) <= 1.0e-3)
        converged = (err1 <= tol1) & (err2 <= tol2) | smalle2
        result = np.where(converged, E2 * 1.0, E1 + 1.0 / ss)
        abserr = err1 + err2 + np.where(converged, tol2 * 10, abs(result-E2))
    if symmetric and len(result) > 1:
        return result[:-1], abserr[1:]
    return result, abserr


class Richardson(object):
    """
    Extrapolates as sequence with Richardsons method

    Notes
    -----
    Suppose you have series expansion that goes like this

    L = f(h) + a0 * h^p_0 + a1 * h^p_1+ a2 * h^p_2 + ...

    where p_i = order + step * i  and f(h) -> L as h -> 0, but f(0) != L.

    If we evaluate the right hand side for different stepsizes h
    we can fit a polynomial to that sequence of approximations.
    This is exactly what this class does.

    Example
    -------
    >>> import numpy as np
    >>> import numdifftools as nd
    >>> n = 3
    >>> Ei = np.zeros((n,1))
    >>> h = np.zeros((n,1))
    >>> linfun = lambda i : np.linspace(0, np.pi/2., 2**(i+5)+1)
    >>> for k in np.arange(n):
    ...    x = linfun(k)
    ...    h[k] = x[1]
    ...    Ei[k] = np.trapz(np.sin(x),x)
    >>> En, err, step = nd.Richardson(step=1, order=1)(Ei, h)
    >>> truErr = Ei-1.
    >>> (truErr, err, En)
    (array([[ -2.00805680e-04],
           [ -5.01999079e-05],
           [ -1.25498825e-05]]), array([[ 0.00320501]]), array([[ 1.]]))

    """
    def __init__(self, step_ratio=2.0, step=1, order=1, num_terms=2):
        self.num_terms = num_terms
        self.order = order
        self.step = step
        self.step_ratio = step_ratio

    def _r_matrix(self, num_terms):
        step = self.step
        i, j = np.ogrid[0:num_terms+1, 0:num_terms]
        r_mat = np.ones((num_terms + 1, num_terms + 1))
        r_mat[:, 1:] = (1.0 / self.step_ratio) ** (i*(step*j + self.order))
        return r_mat

    def rule(self, sequence_length=None):
        if sequence_length is None:
            sequence_length = self.num_terms + 1
        num_terms = min(self.num_terms, sequence_length - 1)
        if num_terms > 0:
            r_mat = self._r_matrix(num_terms)
            return linalg.pinv(r_mat)[0]
        return np.ones((1,))

    @staticmethod
    def _estimate_error(new_sequence, old_sequence, steps, rule):
        m, _n = new_sequence.shape

        if m < 2:
            return (np.abs(new_sequence) * EPS + steps) * 10.0
        cov1 = np.sum(rule**2)  # 1 spare dof
        fact = np.maximum(12.7062047361747 * np.sqrt(cov1), EPS * 10.)
        err = np.abs(np.diff(new_sequence, axis=0)) * fact
        tol = np.maximum(np.abs(new_sequence[1:]),
                         np.abs(new_sequence[:-1])) * EPS * fact
        converged = err <= tol
        abserr = err + np.where(converged, tol * 10,
                                abs(new_sequence[:-1]-old_sequence[1:])*fact)
        # abserr = err1 + err2 + np.where(converged, tol2 * 10, abs(result-E2))
        # abserr = s * fact + np.abs(new_sequence) * EPS * 10.0
        return abserr

    def extrapolate(self, sequence, steps):
        return self.__call__(sequence, steps)

    def __call__(self, sequence, steps):
        ne = sequence.shape[0]
        rule = self.rule(ne)
        nr = rule.size - 1
        m = ne - nr
        new_sequence = convolve(sequence, rule[::-1], axis=0, origin=(nr // 2))
        abserr = self._estimate_error(new_sequence, sequence, steps, rule)
        return new_sequence[:m], abserr[:m], steps[:m]


if __name__ == '__main__':
    dea_demo()
    # epsalg_demo()