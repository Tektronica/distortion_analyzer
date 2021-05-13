import timeit

import numpy as np
import math


def msum(iterable):
    "Full precision summation using multiple floats for intermediate values"
    # Rounded x+y stored in hi with the round-off stored in lo.  Together
    # hi+lo are exactly equal to x+y.  The inner loop applies hi/lo summation
    # to each partial so that the list of partial sums remains exact.
    # Depends on IEEE-754 arithmetic guarantees.  See proof of correctness at:
    # www-2.cs.cmu.edu/afs/cs/project/quake/public/papers/robust-arithmetic.ps

    partials = []  # sorted, non-overlapping partial sums
    for x in iterable:
        i = 0
        for y in partials:
            if abs(x) < abs(y):
                x, y = y, x
            hi = x + y
            lo = y - (hi - x)
            if lo:
                partials[i] = lo
                i += 1
            x = hi
        partials[i:] = [x]
    return sum(partials, 0.0)


def main():
    data = np.array([1, 1e100, 1, -1e100] * 10000)
    N = data.size
    print('length:', N)
    print('type:', data.dtype)
    print()

    # ==================================================================================================================
    print('sum --------------------------------------------')
    A = np.sum(data)

    def numpy_sum():
        np.sum(data)

    Aelapsed = round(((timeit.timeit(stmt=numpy_sum,
                                     setup="",
                                     number=100000) / 100000) * 1e3), 3)
    print('numpy sum:', A, 'elapsed:', Aelapsed, 'ms')

    # ------------------------------------------------------------------------------------------------------------------
    B = math.fsum(data)

    def math_fsum():
        math.fsum(data)

    Belapsed = round(((timeit.timeit(stmt=math_fsum,
                                     setup="",
                                     number=100000) / 100000) * 1e3), 3)
    print('fsum:', B, 'elapsed:', Belapsed, 'ms')

    # ------------------------------------------------------------------------------------------------------------------
    C = msum(data)

    def run_msum():
        msum(data)

    Celapsed = round(((timeit.timeit(stmt=run_msum,
                                     setup="",
                                     number=100000) / 100000) * 1e3), 3)
    print('msum:', C, 'elapsed:', Celapsed, 'ms')
    print()

    # ==================================================================================================================
    print('mean -------------------------------------------')
    AA = np.mean(data)
    print('numpy mean:', AA)

    BB = B / N
    print('fsum mean:', BB)
    print()


if __name__ == "__main__":
    main()
