# The official vantage6 base is hosted on GHCR. Use a public Docker Hub base so
# the image can also be built in environments where GHCR is unavailable; the
# package dependencies below install vantage6-algorithm-tools itself.
FROM python:3.13-slim

# This is a placeholder that should be overloaded by invoking
# docker build with '--build-arg PKG_NAME=...'
ARG PKG_NAME="pc-cohort-builder"

ENV DEBIAN_FRONTEND=noninteractive
ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV LD_LIBRARY_PATH=/usr/lib/jvm/default-java/lib/server

# The python-ohdsi wrappers use rpy2 and OHDSI R packages under the hood.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    default-jdk \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    r-base \
    && R CMD javareconf \
    && Rscript -e "options(repos = c(OHDSI = 'https://ohdsi.github.io/drat/', CRAN = 'https://cloud.r-project.org')); install.packages(c('DatabaseConnector', 'SqlRender', 'CirceR', 'CohortGenerator', 'FeatureExtraction', 'CohortDiagnostics'))" \
    && rm -rf /var/lib/apt/lists/*

# install federated algorithm
COPY . /app
RUN pip install /app

# Set environment variable to make name of the package available within the
# docker image.
ENV PKG_NAME=${PKG_NAME}

# Tell docker to execute `wrap_algorithm()` when the image is run. This function
# will ensure that the algorithm method is called properly.
CMD ["python", "-c", "from vantage6.algorithm.tools.wrap import wrap_algorithm; wrap_algorithm()"]
