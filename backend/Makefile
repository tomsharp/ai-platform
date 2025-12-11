include .env 

.EXPORT_ALL_VARIABLES:
# tf env variables
APP_NAME=inf-api
TAG=latest
TF_VAR_app_name=${APP_NAME}
REGISTRY_NAME=${APP_NAME}
TF_VAR_image=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REGISTRY_NAME}:${TAG}
TF_VAR_region=${AWS_REGION}
# app env variables
MODEL_ID="TinyLlama/TinyLlama-1.1B-Chat-v1.0"


setup-ecr: 
	cd infra/ecr && terraform init && terraform apply -auto-approve

setup-cluster:
	cd infra/cluster && terraform init && terraform apply -auto-approve

setup-infra: setup-ecr setup-cluster

deploy-image:
	cd app && sh deploy.sh

deploy-api:
	aws eks update-kubeconfig --region ${AWS_REGION} --name ${APP_NAME}
	kubectl get svc
	kubectl get namespace ${APP_NAME} >/dev/null 2>&1 || kubectl create namespace ${APP_NAME}
	kubectl config set-context --current --namespace=${APP_NAME}
	@IMAGE=$${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com/$${APP_NAME}:latest; \
	APP_NAME=$(APP_NAME) IMAGE=$$IMAGE MODEL_ID=$(MODEL_ID) \
	envsubst < inference.yml | kubectl -n $(APP_NAME) apply -f -

deploy-all: setup-infra deploy-image deploy-api

teardown-api:
	kubectl -n ${APP_NAME} delete -f inference.yml
	kubectl delete namespace ${APP_NAME}

destroy-ecr:
	cd infra/ecr && terraform destroy -auto-approve

destroy-cluster:
	cd infra/cluster && terraform init && terraform destroy -auto-approve

destroy-all: destroy-cluster destroy-ecr