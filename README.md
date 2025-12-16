# AI Platform
Codebase for deploying AI services.

## Model Inference
### Deploying and Testing
#### Setup
Create a `.env` file that contains your AWS account ID and the deployment region.
```
AWS_ACCOUNT_ID=<aws_account_id>
AWS_REGION=<aws_region>
```
Add this file to two locations: `ai-platform/.env` and  `ai-platform/inference/.env`.

#### Deploy
First, deploy the network and k8s cluster.
```
cd ai-platform
make setup-network-cluster
```
This will deploy the VPC, private/public subnets, internet gateway, NAT gateway, route tables, etc. and spin up our k8s cluster. 

Next, create the ECR repository and build/push the image.
```
cd inference/
make create-repository
make deploy-image
```
Finally, create the k8s namespace and deploy the k8s deployment with the image.
```
make deploy-api
```

#### Test
Let's inspect our k8s deployment to make sure it's running properly. 
```
kubectl get pods
```
There should be one pod running. Grab the pod name and then check the logs to ensure it is up and running.
```
kubectl logs <pod_name>
```

Since our deployment is running in our private subnet as a ClusterIP we will need to use temporary port forwarding to test it from the internet (i.e, our terminal). Here we are forwarding to port 8080.
```
port-forward svc/inference 8080:80 
```
Open another terminal and run tests against the /health and /predict endpoints.
```
curl -X GET "http://127.0.0.1:8080/health"
curl -X POST "http://localhost:8080/predict" -H "Content-Type: application/json" -d '{"text": "Three things to make the perfect omellette are"}'  
```
<br>

### Teardown
Make sure you tear down your infrastructure or you will continue to incur cost on your AWS bill. To do so, run the following (assuming you are still inside the `inference/` directory).
```
make destroy-all
cd ..
make destroy-network-cluster
```