from atlas.agents.l2_strategy.strategy_normalizer import conditions_to_code
from atlas.agents.l2_strategy.coder_agent import CoderAgent
import textwrap

entry = ['rsi_14 < 30', 'macd > macd_signal']
exit_ = ['rsi_14 > 70', 'returns < -0.0002']

block = conditions_to_code(entry, exit_)
print('=== CONDITION BLOCK ===')
print(repr(block))
print()
print(block)

# Simulate _generate_code
class_name = 'Test_Strategy'
generated = textwrap.dedent("""\
import pandas as pd
import numpy as np

class {class_name}:
    def generate_signals(self, df):
        if df is None or df.empty:
            return pd.Series(dtype=int)
        signals = pd.Series(0, index=df.index)

{block}

        signals.loc[entry.fillna(False)] = 1
        signals.loc[exit_.fillna(False)] = -1
        return signals
""".format(class_name=class_name, block=block))

print('=== GENERATED CODE ===')
print(generated)

try:
    compile(generated, '<test>', 'exec')
    print('=== COMPILE: PASSED ===')
except SyntaxError as e:
    print(f'=== COMPILE: FAILED {e} ===')