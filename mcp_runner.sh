#!/bin/bash

# Activate the conda environment
eval "$(conda shell.bash hook)"
conda activate pool

# Run the MCP server
cd "$(dirname "$0")"
python mcp/run.py 