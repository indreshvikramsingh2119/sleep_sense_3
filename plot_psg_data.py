"""
Plot PSG data from CSV to verify signal positions
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Load the CSV file (no headers)
csv_path = 'extracted_data/human.data.csv'
df = pd.read_csv(csv_path, header=None)

print(f"CSV shape: {df.shape}")
print(f"First few rows:\n{df.head(10)}")
print(f"\nColumn statistics:")
for i in range(df.shape[1]):
    print(f"Column {i}: min={df[i].min()}, max={df[i].max()}, unique={df[i].nunique()}")

# According to user, the format is (with 1 empty column at start):
# Index 0: timestamp (actual column 1)
# Index 1: body_position (actual column 2)
# Index 2: pulse (actual column 3)
# Index 3: spo2 (actual column 4)
# Index 4: body_movement (actual column 5)
# Index 5: airflow (actual column 6)
# Index 6: null (actual column 7)
# Index 7: snoring (actual column 8)
# Index 8: null (actual column 9)
# Index 9: null (actual column 10)

# Extract signals according to user's specification
timestamp = df[1].values
body_position = df[2].values
pulse = df[3].values
spo2 = df[4].values
body_movement = df[5].values
airflow = df[6].values
snoring = df[8].values

# Create time in seconds (relative to first timestamp)
time_seconds = (timestamp - timestamp[0]) / 1000.0  # Convert ms to seconds

# Plot all signals
fig, axes = plt.subplots(8, 1, figsize=(15, 12), sharex=True)
fig.suptitle('PSG Signal Data - Column Position Verification', fontsize=16)

signals = [
    (body_position, 'Body Position', 'blue'),
    (pulse, 'Pulse', 'red'),
    (spo2, 'SpO2', 'green'),
    (body_movement, 'Body Movement', 'purple'),
    (airflow, 'Airflow', 'orange'),
    (snoring, 'Snoring', 'brown'),
]

for idx, (signal, name, color) in enumerate(signals):
    axes[idx].plot(time_seconds, signal, color=color, linewidth=0.5)
    axes[idx].set_ylabel(name, fontsize=10)
    axes[idx].grid(True, alpha=0.3)
    axes[idx].set_title(f'{name} (Column {idx+2})', fontsize=9)

axes[-1].set_xlabel('Time (seconds)', fontsize=12)
plt.tight_layout()
plt.savefig('psg_signal_plot.png', dpi=150)
print("\n✅ Plot saved to psg_signal_plot.png")

# Print signal statistics
print("\n=== Signal Statistics ===")
print(f"Body Position: min={body_position.min()}, max={body_position.max()}, unique={np.unique(body_position)}")
print(f"Pulse: min={pulse.min()}, max={pulse.max()}")
print(f"SpO2: min={spo2.min()}, max={spo2.max()}")
print(f"Body Movement: min={body_movement.min()}, max={body_movement.max()}, unique={np.unique(body_movement)}")
print(f"Airflow: min={airflow.min()}, max={airflow.max()}")
print(f"Snoring: min={snoring.min()}, max={snoring.max()}")
