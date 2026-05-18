import pandas as pd
import numpy as np

# Mock df
df = pd.DataFrame({
    'rsi_14': [30, 40, 50, 60, 70],
    'macd': [1, 2, 3, 4, 5],
    'macd_signal': [1.5, 1.5, 1.5, 1.5, 1.5]
})

entry = (
    (df['rsi_14'] < 40)
    & (df['macd'] > df['macd_signal'])
)
exit_ = (
    (df['rsi_14'] > 60)
)

signals = pd.Series(0, index=df.index)

# Apply entries
signals.loc[entry.fillna(False)] = 1

# Apply exits
signals.loc[exit_.fillna(False)] = -1

# Neutralize overlaps
overlap = entry & exit_
signals.loc[overlap.fillna(False)] = 0

print(signals)
