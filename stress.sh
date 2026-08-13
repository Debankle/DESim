#!/bin/bash

if [ -z "$1" ]; then
	echo "Usage: $0 <BEARER_TOKEN>"
	exit 1
fi

TOKEN="$1"

for i in {1..30}; do
	curl -X POST "https://desim.cab432.com/v1/simulations" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "equation": "heat",
    "parameters": {
      "nx": 600,
      "ny": 595,
      "dx": 0.1,
      "dy": 0.1,
      "theta": 0.5,
      "dt": 0.01,
      "steps": 75,
      "alpha": 1.0,
      "ic": {
        "type": "constant",
        "value": 0
      },
      "bc": {
        "left": ["neumann0", 100],
        "right": ["dirichlet", 0],
        "top": ["dirichlet", 0],
        "bottom": ["dirichlet", 0]
      }
    },
    "private": false
  }'
done
