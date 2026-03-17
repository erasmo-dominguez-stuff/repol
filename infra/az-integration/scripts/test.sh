#!/usr/bin/env bash
set -euo pipefail

# Wait for Azure Functions to be ready
for i in {1..30}; do
  if curl -sf http://localhost:7071/api/health > /dev/null; then
    echo "Azure Functions backend is ready"
    break
  fi
  echo "Waiting for Azure Functions backend at http://localhost:7071... ($i/30)"
  sleep 2
done

# Example: test audit endpoint (adjust as needed)
curl -sf http://localhost:7071/api/audit?limit=5 | jq . || echo "No audit events yet"
