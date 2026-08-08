#!/bin/sh
set -eu

python -c "from app.core.config import get_settings; from app.migrations import upgrade_database; upgrade_database(get_settings().database_url)"

exec "$@"
