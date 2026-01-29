#!/bin/bash
ssh -4 ubuntu@yernur-vm1.sin.cvut.cz "cd ~/football-prod && docker-compose run --rm app python -c \"import sys; sys.path.append('/app'); print('Attempting import...'); import app.api.main; print('Import Success')\"" > remote_import_test.txt 2>&1
echo "Remote test finished."
