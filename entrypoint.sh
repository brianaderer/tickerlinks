#!/bin/bash
set -e

if [ -d "migrations" ]; then
    echo "Running database migrations..."
    flask db upgrade || echo "Migration failed or already up to date"
    echo "Running seed..."
    flask seed || echo "Seed failed, continuing anyway"
else
    echo "No migrations directory found, skipping migrations."
fi

exec "$@"
