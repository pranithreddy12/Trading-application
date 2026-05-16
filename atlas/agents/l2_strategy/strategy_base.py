from abc import ABC, abstractmethod
import pandas as pd

class StrategyBase(ABC):
    strategy_name: str = ""
    strategy_id: str = ""
    parameters: dict = {}
    
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Returns pd.Series with values:
        1  = buy signal
        -1 = sell signal  
        0  = hold/no signal
        Index must match df.index
        """
        pass
    
    def get_parameters(self) -> dict:
        return self.parameters
    
    def validate(self) -> bool:
        # Check generate_signals method exists and is callable
        return callable(getattr(self, 'generate_signals', None))
