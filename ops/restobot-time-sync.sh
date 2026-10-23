#!/bin/sh
set -eu

offset=$(/usr/bin/chronyc tracking | /usr/bin/awk '$1 == "System" && $2 == "time" { print $4; exit }')

if /usr/bin/awk -v offset="$offset" 'BEGIN { exit !((offset > 30) || (offset < -30)) }'; then
    /usr/bin/chronyc makestep
fi
