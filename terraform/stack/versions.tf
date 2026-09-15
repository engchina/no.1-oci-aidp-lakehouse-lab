# 必要プロバイダのバージョン制約
# AIDP リソース (oci_ai_data_platform_ai_data_platform) は oracle/oci 9.x 以降に必要
terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 9.0.0"
    }
    external = {
      source  = "hashicorp/external"
      version = ">= 2.2.3"
    }
    local = {
      source  = "hashicorp/local"
      version = ">= 2.4.0"
    }
    template = {
      source  = "hashicorp/template"
      version = ">= 2.2.0"
    }
  }
}
