# The official vantage6 base is hosted on GHCR. Use a public Docker Hub base so
# the image can also be built in environments where GHCR is unavailable; the
# package dependencies below install vantage6-algorithm-tools itself.
FROM python:3.13-slim

LABEL org.opencontainers.image.source="https://github.com/rubensancor/v6_cohort_builder"

# This is a placeholder that should be overloaded by invoking
# docker build with '--build-arg PKG_NAME=...'
ARG PKG_NAME="pc-cohort-builder"

ENV DEBIAN_FRONTEND=noninteractive
ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV LD_LIBRARY_PATH=/usr/lib/jvm/default-java/lib/server

# The python-ohdsi wrappers use rpy2 and OHDSI R packages under the hood.
#
# rJava (pulled in by SqlRender and DatabaseConnector) links against R's own
# compression and regex libraries, so the -dev headers must be present or the
# link step fails with "cannot find -lpcre2-8 / -ldeflate / -llzma / -lbz2".
# R does not abort a build when a package fails to install, which is how an
# image without any OHDSI package got published; the explicit check below
# makes that a build failure instead.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    default-jdk \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    r-base \
    r-base-dev libpcre2-dev libdeflate-dev liblzma-dev libbz2-dev \
    zlib1g-dev libicu-dev \
    && R CMD javareconf \
    && rm -rf /var/lib/apt/lists/*

# Only the four packages the algorithm imports. FeatureExtraction and
# CohortDiagnostics are not needed to generate a cohort and roughly triple
# the build (see pc-cohort-builder/rconvert.py).
RUN Rscript -e ' \
  options(repos = c(OHDSI = "https://ohdsi.github.io/drat/", CRAN = "https://cloud.r-project.org"), Ncpus = 3); \
  pkgs <- c("SqlRender", "DatabaseConnector", "CirceR", "CohortGenerator"); \
  install.packages(pkgs); \
  missing <- pkgs[!pkgs %in% rownames(installed.packages())]; \
  if (length(missing)) stop("R packages failed to install: ", paste(missing, collapse = ", ")); \
  cat("OHDSI R packages installed:", paste(pkgs, collapse = " "), "\n") \
'

# DatabaseConnector needs the JDBC driver jar for PostgreSQL at runtime.
ENV DATABASECONNECTOR_JAR_FOLDER=/opt/jdbc
RUN Rscript -e 'DatabaseConnector::downloadJdbcDrivers("postgresql", pathToDriver = "/opt/jdbc")'

# install federated algorithm
COPY . /app
RUN pip install /app

# Fail the build if the OHDSI path cannot even be imported. python-ohdsi loads
# each R package on import, so this catches a missing package before a node
# does.
RUN python -c "import importlib; \
    importlib.import_module('pc-cohort-builder.cohort')._load_ohdsi_modules(); \
    from ohdsi import circe; print('python-ohdsi import OK')"

# Set environment variable to make name of the package available within the
# docker image.
ENV PKG_NAME=${PKG_NAME}

# Tell docker to execute `wrap_algorithm()` when the image is run. This function
# will ensure that the algorithm method is called properly.
CMD ["python", "-c", "from vantage6.algorithm.tools.wrap import wrap_algorithm; wrap_algorithm()"]
