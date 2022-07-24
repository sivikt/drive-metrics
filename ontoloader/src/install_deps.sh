#!/bin/bash

git clone git@bitbucket.org:diamsvic/ontologies.git ../ontologies

pip3 install -e 'git+git@bitbucket.org:diamsvic/dms-localized-microservices.git#egg=dms-shared&subdirectory=shared'
pip3 install -r requirements.txt