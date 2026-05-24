from random import Random
from typing import Optional
from xxhash import xxh64_intdigest

# Import the OrderedHashRemovedBuckets implementation
from ordered_hash_removed_buckets import OrderedHashRemovedBuckets

MASK_32 = 0xFFFFFFFF
MASK_64 = 0xFFFFFFFFFFFFFFFF


class SplitMix64:
    def __init__(self, seed: int = 0) -> None:
        self.state = seed & MASK_64

    def reset(self, seed: int) -> None:
        self.state = seed & MASK_64

    def next_long(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK_64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK_64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK_64
        return (z ^ (z >> 31)) & MASK_64


def _floor_log2(x: int) -> int:
    return x.bit_length() - 1


def _mask_for_n(n: int) -> int:
    if n <= 1:
        return 0
    return (1 << ((n - 1).bit_length())) - 1


def jumpback_hash(k: int, n: int) -> int:
    if n <= 1:
        return 0

    prg = SplitMix64(k & MASK_64)
    v = prg.next_long()

    v0 = v & MASK_32
    v1 = (v >> 32) & MASK_32

    u = (v0 ^ v1) & _mask_for_n(n)

    while u != 0:
        q = 1 << _floor_log2(u)
        s = u.bit_count() & 1
        if s == 0:
            b = q + (v0 & (q - 1))
        else:
            b = q + (v1 & (q - 1))

        while True:
            if b < n:
                return b
            w = prg.next_long()
            b = (w & MASK_32) & ((q << 1) - 1)
            if b < q:
                break
            if b < n:
                return b
            b = ((w >> 32) & MASK_32) & ((q << 1) - 1)
            if b < q:
                break

        u ^= q

    return 0

class MadsEngine:
    def __init__(self, working_set: int, capacity: int, seed: int = None):
        """
        Initialize MadsHash engine.
        
        Args:
            working_set: Number of initially working buckets
            capacity: Overall capacity (maximum number of buckets)
            seed: Random seed for consistent hashing
        """
        if working_set < 1:
            raise ValueError("Must have at least one working bucket")
        if capacity < working_set:
            raise ValueError("Capacity must be >= working set size")
        
        self.size = working_set
        self.capacity = capacity
        
        if seed is None:
            seed = 0
        self.seed = int(seed)
        
        # Track failed buckets (True = failed, False = working)
        self.failed = [False] * capacity
        
        # Initialize removed buckets tracker
        self.removed_buckets = OrderedHashRemovedBuckets()
        
        # Mark non-working buckets as failed and add to removed set
        for b in range(working_set, capacity):
            self.failed[b] = True
            self.removed_buckets.add(b)
    
    def lookup(self, key: int) -> int:
        """
        Find a working bucket for the given key using MadsHash algorithm.
        
        Args:
            key: The key to hash
            
        Returns:
            Index of the bucket where the key should be mapped
        """
        # Step 1: Use consistent hashing for initial bucket selection
        initial_bucket = jumpback_hash(key, self.size)
        
        if not self.failed[initial_bucket]:
            return initial_bucket
        
        # Step 2: Random fallback using key as seed for reproducibility
        random_gen = Random(xxh64_intdigest(str(key).encode(), self.seed))
        
        while True:
            bucket = random_gen.randint(0, self.capacity - 1)
            if not self.failed[bucket]:
                return bucket
    
    def add(self, shard_id: int = None) -> int:
        if shard_id is not None:
            # Try to reuse specific bucket
            if not self.failed[shard_id]:
                raise ValueError(f"Bucket {shard_id} is not failed (not available for reuse)")
            if not self.removed_buckets.remove(shard_id):
                raise ValueError(f"Bucket {shard_id} not in removed set")
            bucket = shard_id
        elif self.removed_buckets.is_empty():
            # No removed buckets available, create new one
            if self.size >= self.capacity:
                raise OverflowError("No room for more buckets")
            bucket = self.size
            # Expand capacity if needed
            if bucket >= len(self.failed):
                self._expand_capacity(bucket + 1)
        else:
            # Get bucket from removed set
            bucket = self.removed_buckets.poll_next()
        
        # Activate the bucket
        self.failed[bucket] = False
        self.size += 1
        return bucket
    
    def remove(self, shard_id: int) -> int:
        """
        Remove a bucket from the working set.
        
        Args:
            shard_id: Bucket ID to remove
            
        Returns:
            Index of the removed bucket
        """
        if self.failed[shard_id]:
            return shard_id  # Already failed
        
        # Special case: removing the last bucket
        if shard_id == self.capacity - 1 and self.removed_buckets.is_empty():
            self.size -= 1
            self.failed[shard_id] = False  # Clear failed flag
            self.capacity -= 1
            return shard_id
        
        # Normal case: mark as failed and add to removed set
        self.size -= 1
        self.failed[shard_id] = True
        self.removed_buckets.add(shard_id)
        return shard_id
    
    def _expand_capacity(self, new_capacity: int):
        """
        Expand the capacity of the engine.
        
        Args:
            new_capacity: New capacity size
        """
        # Expand failed array
        new_failed = [True] * new_capacity
        for i in range(len(self.failed)):
            new_failed[i] = self.failed[i]
        self.failed = new_failed
        self.capacity = new_capacity


class MadsHasher:
    """
    Wrapper class for MadsHash algorithm providing consistent interface.
    
    This class follows the same interface pattern as other consistent hashing
    implementations in this directory (DXHash, AnchorHash, MementoHash).
    """
    
    def __init__(self, working_set: int, capacity: int, seed: int = None):
        """
        Initialize MadsHash consistent hashing.
        
        Args:
            working_set: Number of initially working resources
            capacity: Overall capacity (maximum number of resources)
            seed: Random seed for consistent hashing
        """
        if working_set < 1:
            raise ValueError("Must have at least one working resource")
        if capacity < working_set:
            raise ValueError("Capacity must be >= working set size")
        
        if seed is None:
            seed = 0
        self.seed = int(seed)
        
        self.working_set_size = int(working_set)
        self.capacity = int(capacity)
        
        self.engine = MadsEngine(working_set, capacity, seed)
        
        self.name = f"MadsHash (w={working_set}, a={capacity})"
    
    def getShard(self, key: str) -> int:
        """
        Get the shard/resource for a given key.
        
        Args:
            key: The key to hash
            
        Returns:
            Index of the shard where the key should be mapped
        """
        k = xxh64_intdigest(key, self.seed)
        return self.engine.lookup(k)
    
    def addShard(self, shard_id: int = None) -> int:
        """
        Add a new shard/resource to the working set.
        
        Args:
            shard_id: Specific shard ID to reuse (optional)
            
        Returns:
            Index of the added shard
            
        Raises:
            OverflowError: If no more shards are available
            ValueError: If specified shard_id is not available
        """
        return self.engine.add(shard_id)
    
    def dropShard(self, shard_id: int) -> int:
        """
        Remove a shard/resource from the working set.
        
        Args:
            shard_id: Shard ID to remove
            
        Returns:
            Index of the removed shard
        """
        return self.engine.remove(shard_id)


# For backward compatibility and easier testing
def create_mads_hasher(working_set: int, capacity: int, seed: int = None) -> MadsHasher:
    """
    Factory function to create a MadsHasher instance.
    
    Args:
        working_set: Number of initially working resources
        capacity: Overall capacity
        seed: Random seed
        
    Returns:
        Configured MadsHasher instance
    """
    return MadsHasher(working_set, capacity, seed)