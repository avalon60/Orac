# --------------------------------------------------------------------
# Oracle Free 23ai + APEX + ORDS + SQLcl Dockerfile for Orac (Linux only)
# Author: Clive Bostock
# Date: 2025-07-29
# --------------------------------------------------------------------

# ✅ Full version (not lite) — includes Java, sqlplus, and other tools
FROM container-registry.oracle.com/database/free:latest

# Build-time args only — values injected by bake
ARG ORACLE_BASE
ARG ORAC_HOME
ARG APEX_VERSION
ARG ORDS_VERSION
ARG SQLCL_VERSION
ARG ORACLE_PDB

# Set runtime env
ENV ORACLE_BASE=${ORACLE_BASE} \
    ORAC_HOME=${ORAC_HOME} \
    ORACLE_PDB=${ORACLE_PDB} \
    APEX_VERSION=${APEX_VERSION} \
    ORDS_VERSION=${ORDS_VERSION} \
    SQLCL_VERSION=${SQLCL_VERSION}

# Switch to root for setup
USER root

# Create required internal directories
RUN mkdir -p \
    ${ORAC_HOME}/bin \
    ${ORAC_HOME}/etc \
    ${ORAC_HOME}/ords \
    ${ORAC_HOME}/ords/params \
    ${ORAC_HOME}/scripts/orac_sql \
    ${ORAC_HOME}/setup/apex \
    ${ORAC_HOME}/setup/ords \
    ${ORAC_HOME}/setup/sqlcl \
    ${ORAC_HOME}/logs

# Copy deployment scripts and binary resources
COPY --chown=54321 resources/docker/oracle/setup   ${ORACLE_BASE}/scripts/setup/
COPY --chown=54321 resources/docker/oracle/startup ${ORACLE_BASE}/scripts/startup/
COPY --chown=54321 resources/docker/oracle/bin     ${ORAC_HOME}/bin
COPY --chown=54321 resources/docker/oracle/etc     ${ORAC_HOME}/etc

# Copy workspace SQL files
COPY --chown=54321 resources/docker/oracle/apex_sql ${ORAC_HOME}/setup/apex
RUN chmod 644 ${ORAC_HOME}/setup/apex/*.sql 

# Ensure startup and bin scripts are executable
RUN chmod +x  ${ORACLE_BASE}/scripts/startup/*.sh 
RUN chmod 644 ${ORACLE_BASE}/scripts/setup/*.sql 
RUN chmod +x  ${ORAC_HOME}/bin/*.sh

# Switch to root to chmod before extracting as oracle
USER root

# Ensure oracle can write to staging before switching
RUN chmod -R 777 ${ORAC_HOME}/setup/apex
RUN chmod -R 777 ${ORAC_HOME}/setup/ords
RUN chmod -R 777 ${ORAC_HOME}/setup/sqlcl

# Ensure we can read/write logs
RUN chmod 777 ${ORAC_HOME}
RUN chmod -R 777 ${ORAC_HOME}/ords
RUN chmod 777 ${ORAC_HOME}/logs

# Switch to oracle for safe downloads
USER oracle

# Download and extract APEX to staging
RUN set -e && \
  echo "📦 Downloading APEX ${APEX_VERSION}..." && \
  curl -sL -o /tmp/apex.zip \
    "https://download.oracle.com/otn_software/apex/apex_${APEX_VERSION}.zip" && \
  unzip -q /tmp/apex.zip -d ${ORAC_HOME}/setup/apex || (echo "❌ APEX unzip failed" && ls -lh /tmp/apex.zip && exit 1) && \
  rm -f /tmp/apex.zip

# Download and extract ORDS to staging
RUN set -e && \
  echo "📦 Downloading ORDS ${ORDS_VERSION}..." && \
  curl -sL -o /tmp/ords.zip \
    "https://download.oracle.com/otn_software/java/ords/ords-${ORDS_VERSION}.zip" && \
  unzip -tq /tmp/ords.zip || (echo "❌ ORDS zipfile corrupt or HTML!" && head -20 /tmp/ords.zip && exit 1) && \
  unzip -q /tmp/ords.zip -d ${ORAC_HOME}/ords && \
  rm -f /tmp/ords.zip

# Download and extract SQLcl to staging
RUN set -e && \
  echo "📦 Downloading SQLcl ${SQLCL_VERSION}..." && \
  curl -sL -o /tmp/sqlcl.zip \
    "https://download.oracle.com/otn_software/java/sqldeveloper/sqlcl-${SQLCL_VERSION}.zip" && \
  unzip -q /tmp/sqlcl.zip -d ${ORAC_HOME}/setup/sqlcl || (echo "❌ SQLcl unzip failed" && ls -lh /tmp/sqlcl.zip && exit 1) && \
  rm -f /tmp/sqlcl.zip


# Switch to root to install system packages
USER root

# Install Java 17
USER root
# Install Java 17 manually from Adoptium (recommended for slim Oracle base images)
ARG JDK_VERSION=17.0.11+9
ARG JDK_BASE_URL=https://github.com/adoptium/temurin17-binaries/releases/download
ARG JDK_FILENAME=OpenJDK17U-jdk_x64_linux_hotspot_17.0.11_9.tar.gz
ARG JDK_URL=${JDK_BASE_URL}/jdk-17.0.11%2B9/${JDK_FILENAME}



RUN curl -L -o /tmp/${JDK_FILENAME} ${JDK_URL} && \
    mkdir -p /usr/lib/jvm && \
    tar -xzf /tmp/${JDK_FILENAME} -C /usr/lib/jvm && \
    rm /tmp/${JDK_FILENAME}

# Set Java 17 as default
ENV JAVA_HOME=/usr/lib/jvm/jdk-17.0.11+9
ENV PATH="${JAVA_HOME}/bin:$PATH"

# Switch back to oracle user
USER oracle

# Expose ports for database and ORDS
EXPOSE 1521 8080 8888

