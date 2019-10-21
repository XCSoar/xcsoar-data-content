#!/bin/bash

cd $TRAVIS_BUILD_DIR

openssl aes-256-cbc -K $encrypted_6262a71f0865_key -iv $encrypted_6262a71f0865_iv -in xcsoar-data-repository_rsa.enc -out xcsoar-data-repository_rsa -d

eval "$(ssh-agent -s)"
chmod 600 xcsoar-data-repository_rsa
ssh-add xcsoar-data-repository_rsa

ssh-keyscan -p ${DEPLOY_PORT} ${DEPLOY_HOST} > ~/.ssh/known_hosts 

rsync -av -e "ssh -p ${DEPLOY_PORT} -i xcsoar-data-repository_rsa" ./waypoints/ ${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/waypoints/ --delete 
rsync -av -e "ssh -p ${DEPLOY_PORT} -i xcsoar-data-repository_rsa" ./waypoints-special/ ${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/waypoints-special/ --delete 
rsync -av -e "ssh -p ${DEPLOY_PORT} -i xcsoar-data-repository_rsa" ./airspaces/ ${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/airspaces/ --delete

