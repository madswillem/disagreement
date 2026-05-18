from typing import List, Tuple
from random import randint

from xxhash import xxh64_intdigest

class AnchorHash:
    """
    The brain of AnchorHash, implements a consistent hash (int key --> bucket index)
    """

    def __init__(self, a: int, w: int) -> None:
        """Creates an AnchorHash Object

        Assumes int buckets and int keys

        Args:
            a:      size of anchor set
            w:      size of working set

        Returns:
            AnchorHash object
        """
        self.M = a
        self.N = a

        # anchor Set
        self.A = [0 for _ in range(a)]

        # working set
        self.W = [x for x in range(a)]

        # last bucket location
        self.L = [x for x in range(a)]

        # successor
        self.K = [x for x in range(a)]

        # removed buckets stack
        self.R = []

        # for i in reversed(range(w, a)):
        #     self.remove_bucket(i)
        for i in range(w, a):
            self.pop_bucket()

    def get_bucket(self, k: int) -> int:
        """Calculates bucket for key

        :param k: key, assumed to be uniform (already hashed)
        :return: assigned bucket
        """
        # uncomment next line if key not already hashed
        # k = xxh64_intdigest(bin(k), k)
        b = k % self.M
        while self.A[b] > 0:  # b is removed
            # next line is like random(seed=k,b)
            # could instead use: k = int(0xFFFFFFFFFFFFFFFF & (k * 2862933555777941757 + 1))
            k = xxh64_intdigest(bin(k)+bin(b), k)
            h = k % self.A[b]
            while self.A[h] >= self.A[b]:  # b removed prior to h
                h = self.K[h]
            b = h
        return b

    def add_bucket(self) -> int:
        """Add a new bucket. The algorithm chooses the new bucket number

        :return: new bucket
        """
        b = self.R.pop()
        self.A[b] = 0
        self.L[self.W[self.N]] = self.N
        self.W[self.L[b]] = b
        self.K[b] = b
        self.N += 1
        return b

    def remove_bucket(self, b: int) -> None:
        """Remove a working bucket

        :param b: bucket to remove
        """
        self.N -= 1
        self.A[b] = self.N
        self.W[self.L[b]] = self.W[self.N]
        self.L[self.W[self.N]] = self.L[b]
        self.K[b] = self.W[self.N]
        self.R.append(b)
        
    def pop_bucket(self):
        """Remove bucket with highest location

        :return: removed bucket
        """
        self.N -= 1
        b = self.W[self.N]
        self.A[b] = self.N
        self.R.append(b)
        return b

class AnchorHasher():
    def __init__(self, working_set: List[str], capacity: int, seed: int) -> None:
        """Creates an AnchorHash Object

        Args:
            working_set:    list of working set resource
            capacity:       capacity of anchor set
            seed:           random seed to use with `xxhash` (in a distributed system, all must use same seed)

        Returns:
            Anchor wrapper object
        """
        if seed is None:
            self.seed = randint(0, 2**32 - 1)
        else:
            self.seed = seed
        
        if len(working_set) < 1:
            raise ValueError("Must have at least one working resource")
        w = len(working_set)
        a = capacity
        self.M = working_set + ["" for _ in range(w, a)]
        self.M_inverse = dict([(resource, bucket) for (bucket, resource) in enumerate(self.M[:w])])
        self.anchor = AnchorHash(a=a, w=w)
        self.name = "AnchorHash (w={w}, a={a})".format(w=w, a=a)
    
    ## used to be like this:
    ## def getShard(self, key: str) -> Tuple[str, int]
    def getShard(self, key: str) -> int:
        k = xxh64_intdigest(key, self.seed)
        b = self.anchor.get_bucket(k)
        return b
    def addShard(self, b: int) -> int:
        if self.anchor.N == self.anchor.M:
            raise OverflowError("No room for more buckets")

        b = self.anchor.add_bucket()
        return b
    def dropShard(self, b: int = None) -> Tuple[int, int]:
        if b is not None:
            self.anchor.remove_bucket(b)
        else:
            b = self.anchor.pop_bucket()

        return b