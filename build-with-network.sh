#!/bin/bash
# Build with host network to bypass Docker DNS issues
export DOCKER_BUILDKIT=1
docker build --network=host -f ocr-service/Dockerfile -t vine-suite-ocr-service ./ocr-service
