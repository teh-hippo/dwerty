FROM debian:trixie-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      python3 \
      python3-pip \
      python3-venv \
      git \
      build-essential \
      gcc-arm-none-eabi \
      dfu-util \
      dos2unix \
      libnewlib-arm-none-eabi \
      libusb-1.0-0 \
      libhidapi-libusb0 \
      ca-certificates \
      pkg-config \
      && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/qmk-venv && \
    /opt/qmk-venv/bin/pip install --no-cache-dir qmk appdirs

ENV PATH="/opt/qmk-venv/bin:${PATH}"

# Ensure the venv stays in PATH even under login shells (bash -l),
# which source /etc/profile and overwrite PATH.
RUN echo 'export PATH="/opt/qmk-venv/bin:${PATH}"' > /etc/profile.d/qmk-venv.sh

WORKDIR /workspace
