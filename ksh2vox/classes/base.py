from abc import ABC, abstractmethod

class VoxEntity(ABC):
    @abstractmethod
    def to_vox_string(self) -> str:
        pass
