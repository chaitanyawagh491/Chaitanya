from abc import ABC, abstractmethod

class IEngineController(ABC):
    @abstractmethod
    def start(self) -> None:
        pass
        
    @abstractmethod
    def shutdown(self) -> None:
        pass

class IAuthService(ABC):
    @abstractmethod
    def initialize(self) -> bool:
        pass
        
    @abstractmethod
    def check_connectivity(self) -> dict:
        pass

class IApiService(ABC):
    @abstractmethod
    def query(self, text: str) -> str:
        pass

class IOverlayService(ABC):
    @abstractmethod
    def display_message(self, text: str) -> bool:
        pass

class IInputService(ABC):
    @abstractmethod
    def start_listening(self) -> None:
        pass
        
    @abstractmethod
    def stop_listening(self) -> None:
        pass

class IStorageService(ABC):
    @abstractmethod
    def load(self) -> None:
        pass
        
    @abstractmethod
    def save(self) -> None:
        pass
