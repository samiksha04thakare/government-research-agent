#!/usr/bin/env bash
set -e

echo "==================================================="
echo "Starting AI Government Research Agent..."
echo "Unified Frontend & Backend on: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "==================================================="

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
