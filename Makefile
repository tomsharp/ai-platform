include .env 

.EXPORT_ALL_VARIABLES:
APP_NAME=ai-platform
# tf env variables
TF_VAR_app_name=${APP_NAME}
TF_VAR_image=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${APP_NAME}:latest
TF_VAR_region=${AWS_REGION}

setup-network-cluster:
	cd infra/network-cluster && terraform init && terraform apply -auto-approve

destroy-network-cluster:
	cd infra/network-cluster && terraform init && terraform destroy -auto-approve