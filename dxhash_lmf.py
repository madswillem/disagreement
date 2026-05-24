from random import randint
from collections import deque
from xxhash import xxh64_intdigest
from typing import Optional

MASK_32 = 0xFFFFFFFF
MASK_64 = 0xFFFFFFFFFFFFFFFF

class DXHashLMF():
    def __init__(self, ns_array, seed: int = None) -> None:
        """
        Initialize DXHash with an NSArray (list of 0/1 values)
        1 = active node, 0 = inactive node
        """
        self.NSArray = ns_array[:]  # copy
        self.IQueue = deque()
        self.Init(ns_array)
        self.name = "DxHash ({l})".format(l=len(ns_array))

        # Parameters for the LCG (common constants)
        self._a = 1664525
        self._c = 1013904223
        self._m = 2 ** 32
        if seed is None:
            self.seed = randint(0, 2**32 - 1)
        else:
            self.seed = seed

    def R(self, r: int) -> int:
        """Pseudo-random number generator (LCG)."""
        return (self._a * r + self._c) % self._m

    # Function Lookup(k)
    def getShard(self, record_id: str) -> int:
        """Find a working (active) node for a given key."""
        # Initialize r as an integer derived from the record_id
        r=xxh64_intdigest(record_id, self.seed)
        while True:
            r = self.R(r)
            nID = r % len(self.NSArray)
            if self.NSArray[nID] == 1:
                return nID

    # Function AddNode()
    def addShard(self, shard_id: int = None):
        """Find an inactive node and activate it."""
        r=xxh64_intdigest(shard_id, self.seed)
        while True:
            r = self.R(r)
            nID = r % len(self.NSArray)
            if self.NSArray[nID] == 0:
                self.NSArray[nID] = 1
                return 

    # Function RmNode(nID)
    def dropShard(self, shard_id: int):
        """Deactivate the given node and push it back into IQueue."""
        if self.NSArray[shard_id] == 0:
            return  # already inactive
        self.NSArray[shard_id] = 0

    # Function Init(NSArray)
    def Init(self, ns_array):
        """Initialize IQueue from NSArray."""
        pass

class DxHasher:
    def __init__(self, working_set: int, capacity: int, seed: Optional[int] = None) -> None:
        if working_set < 1:
            raise ValueError("Must have at least one working resource")

        if seed is None:
            seed = 0
        self.seed = int(seed) & MASK_64

        self.capacity = int(capacity)
        self.working_set_size = int(working_set)

        if self.capacity < self.working_set_size:
            raise ValueError("Capacity must be >= working set size")
        
        ns_array = [1] * capacity

        self.dx = DXHashLMF(ns_array, seed=self.seed)
        for b in range(self.working_set_size, self.capacity):
            self.dx.remove(b)

        self.name = "DxHash (w={w}, a={a})".format(
            w=self.working_set_size, a=self.capacity
        )

    def getShard(self, key: str) -> int:
        k = xxh64_intdigest(key, self.seed)
        return self.dx.lookup(k)

    def addShard(self, shard_id: Optional[int] = None) -> int:
        if self.dx.n == self.capacity and not self.dx.R:
            raise OverflowError("No room for more buckets")
        return self.dx.add()

    def dropShard(self, shard_id: Optional[int]) -> int:
        if shard_id is None:
            raise ValueError("DxHash requires explicit shard_id for removal")
        self.dx.remove(shard_id)
        return shard_id