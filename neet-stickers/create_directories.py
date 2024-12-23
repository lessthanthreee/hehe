import os

directories = [
    'input',
    'output',
    'output/live2d_layers'
]

for directory in directories:
    os.makedirs(directory, exist_ok=True)
    print(f"Created directory: {directory}")
