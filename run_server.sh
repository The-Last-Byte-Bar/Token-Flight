#!/bin/bash

# Ensure we're in the correct directory
cd "$(dirname "$0")"

# Unset problematic environment variables
unset PYTHONHOME
unset PYTHONPATH

# Source conda initialization
source ~/miniconda3/etc/profile.d/conda.sh

# Activate conda environment
conda activate pool

# Set our own PYTHONPATH
export PYTHONPATH="$PWD:$PWD/src"

# Run the server
exec python mcp/run.py 