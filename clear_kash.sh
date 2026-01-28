#!/usr/bin/env bash
set -e

# + will concatenate the path one after the other
find . -type d -name "*pycache*" -exec rm -rI {} +        
