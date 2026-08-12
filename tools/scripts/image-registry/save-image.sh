#!/bin/bash
FULL_IMAGE=$1
IMAGE_TAG_PAIR="${FULL_IMAGE##*/}"
IMAGE_NAME="${IMAGE_TAG_PAIR%:*}"
TAG="${IMAGE_TAG_PAIR#*:}"

docker login registry.gitlab.com
docker pull registry.gitlab.com/textfactory/hermes/pipeline/$IMAGE_NAME:$TAG
docker tag registry.gitlab.com/textfactory/hermes/pipeline/$IMAGE_NAME:$TAG registry.marganit-1.idf.cts/mazpen-hermes/$IMAGE_NAME:$TAG
docker save registry.marganit-1.idf.cts/mazpen-hermes/$IMAGE_NAME:$TAG | gzip > $IMAGE_NAME-$TAG.tar.gz