include .env 

.EXPORT_ALL_VARIABLES:
APP_NAME=inference
CLUSTER_NAME=ai-platform
# container registry variables
REGISTRY=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
REPOSITORY=ai-platform/$(APP_NAME)
TAG=latest
# tf env variables
TF_VAR_app_name=$(APP_NAME)
TF_VAR_region=$(AWS_REGION)
# containter/app env variables
MODEL_ID ?= TinyLlama/TinyLlama-1.1B-Chat-v1.0


create-repository:
	aws ecr create-repository --repository-name $(REPOSITORY) --region $(AWS_REGION) || true

deploy-image:
	sh deploy.sh

deploy-api:
	aws eks update-kubeconfig --region $(AWS_REGION) --name $(CLUSTER_NAME)
	kubectl get svc
	kubectl get namespace $(APP_NAME) >/dev/null 2>&1 || kubectl create namespace $(APP_NAME)
	kubectl config set-context --current --namespace=$(APP_NAME)
	IMAGE="$(REGISTRY)/$(REPOSITORY):$(TAG)" \
	envsubst < inference.yml | kubectl -n $(APP_NAME) apply -f -
	
deploy-all: create-repository deploy-image deploy-api

destroy-api:
	IMAGE="$(REGISTRY)/$(REPOSITORY):$(TAG)" \
	envsubst < inference.yml | kubectl -n $(APP_NAME) delete -f -
	kubectl delete namespace $(APP_NAME) --ignore-not-found

destroy-repository:
	aws ecr delete-repository --repository-name $(REPOSITORY) --region $(AWS_REGION) --force

destroy-all: destroy-api destroy-repository