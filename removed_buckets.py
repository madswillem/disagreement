# Abstract base class for RemovedBuckets interface
from abc import ABC, abstractmethod

class RemovedBuckets(ABC):
    """
    Tracks buckets removed from the working set and available for reuse.
    """
    
    @abstractmethod
    def is_empty(self) -> bool:
        """
        Returns whether there are any removed buckets available.
        
        Returns:
            True if no removed buckets are tracked
        """
        pass
    
    @abstractmethod
    def add(self, bucket: int) -> None:
        """
        Adds the given removed bucket.
        
        Args:
            bucket: the removed bucket to track
        """
        pass
    
    @abstractmethod
    def remove(self, bucket: int) -> bool:
        """
        Removes the given bucket, if present.
        
        Args:
            bucket: the bucket to remove
            
        Returns:
            True if the bucket was removed
        """
        pass
    
    @abstractmethod
    def poll_next(self) -> int:
        """
        Returns and removes the next bucket to restore.
        
        Returns:
            the next bucket to restore
            
        Raises:
            IndexError: if no removed buckets are available
        """
        pass