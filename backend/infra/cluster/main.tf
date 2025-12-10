provider "aws" {
  region = var.region
  default_tags {
    tags = {
      app = var.app_name
    }
  }
}

module "network" {
  source   = "./network"
  app_name = var.app_name
  region   = var.region
}

module "eks" {
  source             = "./eks"
  app_name           = var.app_name
  region             = var.region
  vpc_id             = module.network.vpc.id
  public_subnet_ids  = [for s in module.network.public_subnets : s.id]
  private_subnet_ids = [for s in module.network.private_subnets : s.id]
  eks_managed_node_groups = {
    cpu = {
      desired_capacity = 1
      min_capacity     = 1
      max_capacity     = 2
      instance_types = ["m6i.xlarge"]
      capacity_type  = "ON_DEMAND"  
      labels = {
        pool = "cpu"
      }
    }
  }
  depends_on         = [module.network]
}


# Outputs
output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}
