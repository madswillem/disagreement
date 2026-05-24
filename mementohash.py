from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from xxhash import xxh64_intdigest


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


def _mix_key_bucket(key: int, bucket: int) -> int:
    x = (key ^ ((bucket + 0x9E3779B97F4A7C15) & MASK_64)) & MASK_64
    x ^= (x >> 30) & MASK_64
    x = (x * 0xBF58476D1CE4E5B9) & MASK_64
    x ^= (x >> 27) & MASK_64
    x = (x * 0x94D049BB133111EB) & MASK_64
    x ^= (x >> 31) & MASK_64
    return x


@dataclass
class _Replacement:
    c: int
    p: int


class MementoHash:
    def __init__(self, initial_node_count: int) -> None:
        if initial_node_count < 1:
            raise ValueError("Must have at least one bucket")
        self.n = int(initial_node_count)
        self.l = self.n
        self.R: Dict[int, _Replacement] = {}

    def remove(self, b: int) -> None:
        if b < 0 or b >= self.n:
            raise ValueError("Bucket out of range")

        if b == self.n - 1 and not self.R:
            self.n -= 1
        else:
            w = self.n - len(self.R)
            self.R[b] = _Replacement(w - 1, self.l)
        self.l = b

    def add(self) -> int:
        if not self.R:
            b = self.n
            self.l = self.n
            self.n += 1
            return b

        b = self.l
        replacement = self.R.pop(b)
        self.l = replacement.p
        return b

    def lookup(self, key: int) -> int:
        b = jumpback_hash(key, self.n)

        while b in self.R:
            replacement = self.R[b]
            wb = replacement.c

            h = _mix_key_bucket(key, b)
            d = h % wb

            while d in self.R and self.R[d].c >= wb:
                d = self.R[d].c

            b = d

        return b

class MementoHasher:
    def __init__(self, working_set, capacity: int, seed: Optional[int] = None) -> None:
        if len(working_set) < 1:
            raise ValueError("Must have at least one working resource")

        if seed is None:
            seed = 0
        self.seed = int(seed) & MASK_64

        self.capacity = int(capacity)
        self.working_set_size = int(len(working_set))

        if self.capacity < self.working_set_size:
            raise ValueError("Capacity must be >= working set size")

        self.memento = MementoHash(self.capacity)
        for b in range(self.working_set_size, self.capacity):
            self.memento.remove(b)

        self.name = "MementoHash (w={w}, a={a})".format(
            w=self.working_set_size, a=self.capacity
        )

    def getShard(self, key: str) -> int:
        k = xxh64_intdigest(key, self.seed)
        return self.memento.lookup(k)

    def addShard(self, shard_id: Optional[int] = None) -> int:
        if self.memento.n == self.capacity and not self.memento.R:
            raise OverflowError("No room for more buckets")
        return self.memento.add()

    def dropShard(self, shard_id: Optional[int]) -> int:
        if shard_id is None:
            raise ValueError("MementoHash requires explicit shard_id for removal")
        self.memento.remove(shard_id)
        return shard_id
