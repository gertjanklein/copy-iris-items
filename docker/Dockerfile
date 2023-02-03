# The IRIS image to use
ARG IMAGE=containers.intersystems.com/intersystems/iris-community:2022.2.0.368.0

FROM $IMAGE

CMD ["--ISCAgent false"]

# The Strix commit to load files to use for testing from
ARG COMMIT="2a547dc4968e1e0cc986df7a959d6d9ce46917f1"

WORKDIR /opt/irisbuild
USER root
RUN chown ${ISC_PACKAGE_MGRUSER}:${ISC_PACKAGE_IRISGROUP} /opt/irisbuild
USER ${ISC_PACKAGE_MGRUSER}

# Get test files
RUN wget -qO Strix.tgz https://github.com/gertjanklein/Strix/archive/${COMMIT}.tar.gz
RUN tar xzf Strix.tgz --strip-components=1 Strix-${COMMIT}/src

# Copy script that loads the files
COPY iris.script iris.script

# Run it
RUN iris start IRIS \
  && iris session IRIS < iris.script \
  && iris stop IRIS quietly
