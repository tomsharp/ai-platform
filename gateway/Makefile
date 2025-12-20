include .env 
.PHONY: db-up db-down db-reset db-seed redis-up redis-down setup-kubectl

.EXPORT_ALL_VARIABLES:
APP_NAME=gateway
K8S_CLUSTER_NAME=ai-platform
REGISTRY=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
REPOSITORY=ai-platform/$(APP_NAME)
TAG=latest

# -- Local --
db-up:
	docker run --name gateway-postgres \
		-e POSTGRES_USER=gateway \
		-e POSTGRES_PASSWORD=gateway \
		-e POSTGRES_DB=gateway \
		-p 5432:5432 \
		-d postgres:16 || true
	@echo "Waiting for Postgres to be ready..."
	@until docker exec gateway-postgres pg_isready -U gateway -d gateway >/dev/null 2>&1; do \
		sleep 1; \
	done
	cd app && python -m seed

db-down:
	docker stop gateway-postgres || true
	docker rm gateway-postgres || true
	docker volume prune -f

redis-up:
	docker run --name gateway-redis -p 6379:6379 -d redis:7 || true

redis-down:
	docker stop gateway-redis || true
	docker rm gateway-redis || true
	docker volume prune -f	

# -- Deploy --
setup-kubectl:
	aws eks update-kubeconfig --region $(AWS_REGION) --name $(K8S_CLUSTER_NAME)
	kubectl get svc
	kubectl get namespace $(APP_NAME) >/dev/null 2>&1 || kubectl create namespace $(APP_NAME)
	kubectl config set-context --current --namespace=$(APP_NAME)

create-repository:
	aws ecr create-repository --repository-name $(REPOSITORY) --region $(AWS_REGION) || true

deploy-image:
	sh image.sh

deploy-redis: setup-kubectl
	helm install gateway-redis bitnami/redis \
		--set architecture=standalone \
		--set auth.enabled=false \
		--namespace $(APP_NAME) || true

deploy-db: setup-kubectl
	helm install gateway-postgres bitnami/postgresql \
		--set architecture=standalone \
		--set auth.username=gateway \
		--set auth.password=$(DB_PASSWORD) \
		--set auth.database=gateway

deploy-gateway: setup-kubectl
	@IMAGE="$(REGISTRY)/$(REPOSITORY):$(TAG)" \
	JWT_SECRET_KEY="$(JWT_SECRET_KEY)" \
	OPENAI_API_KEY="$(OPENAI_API_KEY)" \
	DATABASE_URL=postgresql+asyncpg://gateway:$(DB_PASSWORD)@gateway-postgres:5432/gateway \
	REDIS_URL=redis://gateway-redis-master:6379/0 \
	envsubst < gateway.yaml | kubectl -n $(APP_NAME) apply -f -

deploy-all: create-repository deploy-image deploy-redis deploy-db deploy-gateway


# -- Destroy --
destroy-repository:
	aws ecr delete-repository --repository-name $(REPOSITORY) --region $(AWS_REGION) --force

destroy-redis:
	helm uninstall gateway-redis

destroy-db:
	helm uninstall gateway-postgres

destroy-gateway:
	envsubst < gateway.yaml | kubectl -n $(APP_NAME) delete -f -

destroy-all: destroy-gateway destroy-redis destroy-db destroy-repository