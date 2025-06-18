#!/usr/bin/env bash
set -e

# + will concatenate the path one after the other
find . -type d -name "*cache*" -exec rm -rI {} +        
