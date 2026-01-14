FROM ubuntu:25.10

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y \
      python3 \
      python3-pip \
      python3-venv \
      git \
      build-essential \
      gcc-arm-none-eabi \
      gcc-avr \
      avr-libc \
      avrdude \
      dfu-programmer \
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

WORKDIR /workspace
