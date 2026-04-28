# --------------------------------------------------------------------
# Oracle Free ai database + APEX + ORDS + SQLcl Dockerfile for Orac (Linux only)
# Author: Clive Bostock
# Date: 2025-07-29
# --------------------------------------------------------------------
ARG ORACLE_IMAGE_TAG=23.26.0.0
FROM container-registry.oracle.com/database/free:${ORACLE_IMAGE_TAG}

# Build-time args (injected by bake)
ARG ORACLE_BASE
ARG ORAC_HOME
ARG APEX_VERSION
ARG ORDS_VERSION
ARG SQLCL_VERSION
ARG ORACLE_PDB

# Runtime env
ENV ORACLE_BASE=${ORACLE_BASE} \
    ORAC_HOME=${ORAC_HOME} \
    ORACLE_PDB=${ORACLE_PDB} \
    APEX_VERSION=${APEX_VERSION} \
    ORDS_VERSION=${ORDS_VERSION} \
    SQLCL_VERSION=${SQLCL_VERSION}

# --------------------------------------------------------------------
# Root phase: create stable layout for cached tool downloads
# --------------------------------------------------------------------
USER root

# Create required dirs
RUN mkdir -p \
    ${ORAC_HOME}/bin \
    ${ORAC_HOME}/etc \
    ${ORAC_HOME}/ords/params \
    ${ORAC_HOME}/scripts/orac_sql \
    ${ORAC_HOME}/setup/apex \
    ${ORAC_HOME}/setup/sqlcl \
    ${ORAC_HOME}/app \
    ${ORAC_HOME}/schema \
    ${ORAC_HOME}/logs

# Make oracle the owner of all locations it will write to during build/runtime.
# Keep this before the large downloads so those layers can be reused even when
# repo-tracked SQL or shell scripts change.
RUN chown -R 54321:54321 \
    ${ORAC_HOME}/setup/apex \
    ${ORAC_HOME}/setup/sqlcl \
    ${ORAC_HOME}/ords \
    ${ORAC_HOME}/app \
    ${ORAC_HOME}/schema \
    ${ORAC_HOME}/logs

# --------------------------------------------------------------------
# Fetch APEX / ORDS / SQLcl as oracle
# Keep these downloads ahead of repo COPY steps so Docker can cache them across
# normal application and schema edits.
# --------------------------------------------------------------------
USER oracle

# APEX
RUN set -e && \
  echo "📦 Downloading APEX ${APEX_VERSION}..." && \
  curl -sL -o /tmp/apex.zip \
    "https://download.oracle.com/otn_software/apex/apex_${APEX_VERSION}.zip" && \
  unzip -q /tmp/apex.zip -d ${ORAC_HOME}/setup/apex || (echo "❌ APEX unzip failed" && ls -lh /tmp/apex.zip && exit 1) && \
  rm -f /tmp/apex.zip

# ORDS
RUN set -e && \
  echo "📦 Downloading ORDS ${ORDS_VERSION}..." && \
  curl -sL -o /tmp/ords.zip \
    "https://download.oracle.com/otn_software/java/ords/ords-${ORDS_VERSION}.zip" && \
  unzip -tq /tmp/ords.zip || (echo "❌ ORDS zipfile corrupt or HTML!" && head -20 /tmp/ords.zip && exit 1) && \
  unzip -q /tmp/ords.zip -d ${ORAC_HOME}/ords && \
  rm -f /tmp/ords.zip

# SQLcl
RUN set -e && \
  echo "📦 Downloading SQLcl ${SQLCL_VERSION}..." && \
  curl -sL -o /tmp/sqlcl.zip \
    "https://download.oracle.com/otn_software/java/sqldeveloper/sqlcl-${SQLCL_VERSION}.zip" && \
  unzip -q /tmp/sqlcl.zip -d ${ORAC_HOME}/setup/sqlcl || (echo "❌ SQLcl unzip failed" && ls -lh /tmp/sqlcl.zip && exit 1) && \
  rm -f /tmp/sqlcl.zip

# --------------------------------------------------------------------
# Root phase: install Java 17 (Adoptium)
# Keep this ahead of repo COPY steps for the same caching reason.
# --------------------------------------------------------------------
USER root

ARG JDK_VERSION=17.0.11+9
ARG JDK_BASE_URL=https://github.com/adoptium/temurin17-binaries/releases/download
ARG JDK_FILENAME=OpenJDK17U-jdk_x64_linux_hotspot_17.0.11_9.tar.gz
ARG JDK_URL=${JDK_BASE_URL}/jdk-17.0.11%2B9/${JDK_FILENAME}

RUN curl -L -o /tmp/${JDK_FILENAME} ${JDK_URL} && \
    mkdir -p /usr/lib/jvm && \
    tar -xzf /tmp/${JDK_FILENAME} -C /usr/lib/jvm && \
    rm /tmp/${JDK_FILENAME}

ENV JAVA_HOME=/usr/lib/jvm/jdk-17.0.11+9
ENV PATH="${JAVA_HOME}/bin:$PATH"

# --------------------------------------------------------------------
# Root phase: copy repo resources and set sane perms
# --------------------------------------------------------------------
USER root

# Copy deployment scripts and configs
COPY --chown=54321 resources/docker/oracle/setup   ${ORACLE_BASE}/scripts/setup/
COPY --chown=54321 resources/docker/oracle/startup ${ORACLE_BASE}/scripts/startup/
COPY --chown=54321 resources/docker/oracle/bin     ${ORAC_HOME}/bin
COPY --chown=54321 resources/docker/oracle/etc     ${ORAC_HOME}/etc

# Copy schema (whole tree, once) and set perms (dirs 755, *.sql 644)
COPY --chown=54321 resources/db/schema ${ORAC_HOME}/schema
RUN find ${ORAC_HOME}/schema -type d -exec chmod 755 {} + \
 && find ${ORAC_HOME}/schema -type f -name "*.sql" -exec chmod 644 {} +

# Copy APEX workspace/app SQL (once) and set perms
# COPY --chown=54321 resources/docker/oracle/apex_sql ${ORAC_HOME}/setup/apex
RUN find ${ORAC_HOME}/setup/apex -type d -exec chmod 755 {} + \
 && find ${ORAC_HOME}/setup/apex -type f -name "*.sql" -exec chmod 644 {} +

# Copy app exports and set perms
# COPY --chown=54321 resources/db/app ${ORAC_HOME}/app
# RUN find ${ORAC_HOME}/app -type d -exec chmod 755 {} + \
#  && find ${ORAC_HOME}/app -type f -name "*.sql" -exec chmod 644 {} +

# Ensure we can read/write logs
RUN chmod 755 ${ORAC_HOME}/logs

# Make startup scripts executable
RUN chmod +x  ${ORACLE_BASE}/scripts/startup/*.sh
RUN chmod +x  ${ORAC_HOME}/bin/*.sh
RUN chmod 644 ${ORACLE_BASE}/scripts/setup/*.sql

# Back to oracle
USER oracle

EXPOSE 1521 8080 8888
