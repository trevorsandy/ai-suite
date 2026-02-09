#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 -U postgres -d "$POSTGRES_DB" -c "CREATE SCHEMA IF NOT EXISTS \"$AUTHELIA_SCHEMA\""
