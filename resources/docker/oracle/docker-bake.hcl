group "default" {
  targets = ["orac"]
}

target "orac" {
  // Set the context to the *project root*
  context = "../../../"
  dockerfile = "resources/docker/oracle/Dockerfile"
  tags       = ["oracdb-img:latest"]

  args = {
    ORAC_HOME     = "/home/oracle/orac"
    APEX_VERSION  = "24.1"
    ORDS_VERSION  = "25.2.2.204.0103"
    SQLCL_VERSION = "25.2.2.199.0918"
  }
}

