from typing import List
from removed_buckets import RemovedBuckets


class OrderedHashRemovedBuckets(RemovedBuckets):
    """
    RemovedBuckets implementation backed by primitive sorted hash chains.
    Collision chains are kept in ascending bucket-id order, making polling deterministic.
    """
    
    EMPTY = -1
    INITIAL_CAPACITY = 16
    
    def __init__(self):
        self.heads = [self.EMPTY] * self.INITIAL_CAPACITY
        self.values = [0] * self.INITIAL_CAPACITY
        self.next = [self.EMPTY] * self.INITIAL_CAPACITY
        self.size = 0
        self.next_unused = 0
        self.free = self.EMPTY
    
    def is_empty(self) -> bool:
        return self.size == 0
    
    def add(self, bucket: int) -> None:
        if (self.size + 1) * 4 > len(self.heads) * 3:
            self._rehash(len(self.heads) << 1)
        
        head = self._slot(bucket)
        previous = self.EMPTY
        current = self.heads[head]
        
        while current != self.EMPTY and self.values[current] < bucket:
            previous = current
            current = self.next[current]
        
        if current != self.EMPTY and self.values[current] == bucket:
            return
        
        entry = self._allocate_entry()
        self.values[entry] = bucket
        self.next[entry] = current
        
        if previous == self.EMPTY:
            self.heads[head] = entry
        else:
            self.next[previous] = entry
        
        self.size += 1
    
    def remove(self, bucket: int) -> bool:
        head = self._slot(bucket)
        previous = self.EMPTY
        current = self.heads[head]
        
        while current != self.EMPTY and self.values[current] < bucket:
            previous = current
            current = self.next[current]
        
        if current == self.EMPTY or self.values[current] != bucket:
            return False
        
        if previous == self.EMPTY:
            self.heads[head] = self.next[current]
        else:
            self.next[previous] = self.next[current]
        
        self._release_entry(current)
        self.size -= 1
        return True
    
    def poll_next(self) -> int:
        if self.is_empty():
            raise IndexError("No removed buckets available")
        
        for head in range(len(self.heads)):
            entry = self.heads[head]
            if entry != self.EMPTY:
                bucket = self.values[entry]
                self.heads[head] = self.next[entry]
                self._release_entry(entry)
                self.size -= 1
                return bucket
        
        raise IndexError("No removed buckets available")
    
    def _rehash(self, capacity: int) -> None:
        previous_heads = self.heads
        previous_values = self.values
        previous_next = self.next
        
        self.heads = [self.EMPTY] * capacity
        self.values = [0] * capacity
        self.next = [self.EMPTY] * capacity
        self.next_unused = 0
        self.free = self.EMPTY
        self.size = 0
        
        for head in range(len(previous_heads)):
            current = previous_heads[head]
            while current != self.EMPTY:
                self.add(previous_values[current])
                current = previous_next[current]
    
    def _allocate_entry(self) -> int:
        if self.free != self.EMPTY:
            entry = self.free
            self.free = self.next[entry]
            return entry
        
        entry = self.next_unused
        self.next_unused += 1
        return entry
    
    def _release_entry(self, entry: int) -> None:
        self.next[entry] = self.free
        self.free = entry
    
    def _slot(self, bucket: int) -> int:
        return self._mix(bucket) & (len(self.heads) - 1)
    
    @staticmethod
    def _mix(value: int) -> int:
        hash_val = value
        hash_val ^= hash_val >> 16
        hash_val *= 0x7feb352d
        hash_val ^= hash_val >> 15
        hash_val *= 0x846ca68b
        hash_val ^= hash_val >> 16
        return hash_val