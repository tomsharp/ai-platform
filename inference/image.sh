#!/bin/bash

echo "Logging in to ECR registry"
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $REGISTRY

echo "Building image"
docker build --platform=linux/amd64 -t $REPOSITORY:$TAG .

echo "Tagging image"
docker tag $REPOSITORY:$TAG $REGISTRY/$REPOSITORY:$TAG

echo "Pushing image to ECR"
docker push $REGISTRY/$REPOSITORY:$TAG