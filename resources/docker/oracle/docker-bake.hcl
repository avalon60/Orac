# docker-bake.hcl
variable "ORAC_IMAGE_NAME" { default = "orac" }
variable "ORAC_IMAGE_TAG"  { default = "latest" }

target "orac" {
  context    = "../../../"
  dockerfile = "resources/docker/oracle/Dockerfile"
  tags       = ["${ORAC_IMAGE_NAME}:${ORAC_IMAGE_TAG}"]

  args = {
    ORACLE_BASE   = "/opt/oracle"
    ORACLE_PDB    = "FREEPDB1"
    ORAC_HOME     = "/home/oracle/orac"
    APEX_VERSION  = "24.2"
    ORDS_VERSION  = "25.2.2.204.0103"
    SQLCL_VERSION = "25.2.2.199.0918"
  }
}

