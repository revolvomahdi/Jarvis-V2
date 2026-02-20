from abc import ABC, abstractmethod

class BaseEngine(ABC):
    @abstractmethod
    def generate_response(self, prompt, system_instruction=None, history=[], images=[]):
        pass

    @abstractmethod
    def generate_stream(self, prompt, system_instruction=None, history=[], images=[]):
        pass
