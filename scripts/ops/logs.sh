#!/bin/bash
# Helper script to view logs on production server
# Default to following logs, allow passing "no" to just see end
FOLLOW_FLAG="-f"
if [ "$1" == "no" ]; then
    FOLLOW_FLAG=""
fi

ssh ubuntu@yernur-vm1.sin.cvut.cz "cd football-prod && docker-compose logs --tail=100 -t $FOLLOW_FLAG app"
