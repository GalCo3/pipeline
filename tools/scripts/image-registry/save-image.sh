#!/bin/bash
set -euo pipefail

docker login registry.gitlab.com

for FULL_IMAGE in "$@"; do
  IMAGE_TAG_PAIR="${FULL_IMAGE##*/}"
  IMAGE_NAME="${IMAGE_TAG_PAIR%:*}"
  TAG="${IMAGE_TAG_PAIR#*:}"

  echo "=== Processing $IMAGE_NAME:$TAG ==="

  docker pull registry.gitlab.com/textfactory/hermes/pipeline/$IMAGE_NAME:$TAG
  docker save registry.gitlab.com/textfactory/hermes/pipeline/$IMAGE_NAME:$TAG | gzip > $IMAGE_NAME-$TAG.tar.gz
done