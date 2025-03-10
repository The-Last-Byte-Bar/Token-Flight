#!/bin/bash

# Ensure we're in the project root directory
cd "$(dirname "$0")"

# Add the current directory to Python path
export PYTHONPATH=.

# Run the bonus service with all arguments passed to this script
python src/bonus_service.py "$@" 