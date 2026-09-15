# OCI プロバイダ
# 認証情報（tenancy / user / fingerprint / private_key / region）は
# Resource Manager がデプロイ時に環境変数として注入するため、ここでは明示しない。
provider "oci" {}
