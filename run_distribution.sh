#!/bin/bash

# Ensure we're in the project root directory
cd "$(dirname "$0")" || exit 1

# Add the current directory to Python path
export PYTHONPATH=.

# Make the Python script executable if it isn't already
chmod +x run_distribution.py

# Run the distribution tool with all arguments passed to this script
./run_distribution.py "$@" 