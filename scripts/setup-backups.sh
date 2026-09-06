#!/bin/sh
set -eu

# The production containers run as UID/GID 10001. Run this script as root on
# the Docker host before the first `docker compose up`.
install -d -m 0700 -o 10001 -g 10001 backups
