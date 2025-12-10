variable "app_name" {
  description = "Name of the app."
  type        = string
}
variable "region" {
  description = "AWS region to deploy the network to."
  type        = string
}
variable "vpc_id" {
  description = "ID of the VPC where the ECS will be hosted."
  type        = string
}
variable "public_subnet_ids" {
  description = "IDs of public subnets where the ALB will be attached to."
  type        = list(string)
}
variable "private_subnet_ids" {
  description = "IDs of private subnets where the ECS service will be deployed to."
  type        = list(string)
}
variable eks_managed_node_groups {
  description = "EKS managed node groups configuration."
  type        = map(any)
}