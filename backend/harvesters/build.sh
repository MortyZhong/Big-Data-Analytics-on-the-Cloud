#!/bin/sh
pip install -r ${SRC_PKG}/requirements.txt -t ${SRC_PKG} && cp -r ${SRC_PKG} ${DEPLOY_PKG}

