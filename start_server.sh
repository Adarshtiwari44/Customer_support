#!/bin/bash
echo "🚀 Starting Customer Support AI Server..."
echo ""
echo "Frontend URLs:"
echo "  Chat Interface:   http://localhost:8000/"
echo "  Review Dashboard: http://localhost:8000/review"
echo "  API Docs:         http://localhost:8000/docs"
echo ""
uvicorn customer_support.api.main:app --reload --host 0.0.0.0 --port 8000
