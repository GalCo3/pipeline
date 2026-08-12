#!/bin/bash

IMAGE_FILE=$1
BASE="${IMAGE_FILE%.tar.gz}"

REGISTRY_URL="registry.marganit-1.idf.cts"
REGISTRY_ORGANIZATION="mazpen-hermes"

IMAGE_TAG="${BASE##*-}"

IMAGE_NAME="${BASE%-*}"

echo "importing image ${IMAGE_NAME} with tag ${IMAGE_TAG}"

docker load -i $IMAGE_FILE

echo "image loaded sucessfully. pushing to marganit..."

docker push $REGISTRY_URL/$REGISTRY_ORGANIZATION/$IMAGE_NAME:$IMAGE_TAG

echo "pushed successfully! go to metzuda and sync!"