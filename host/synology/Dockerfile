FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
       adb fastboot usbutils ca-certificates python3 python3-serial unzip \
    && rm -rf /var/lib/apt/lists/*

# Release 0.0.8; downloaded separately and verified before entering build context.
COPY echolocal_linux_x86_64 /usr/local/bin/echoctl
RUN echo 'a350601761bc52ef865eba63b7117e6a63315c9541a780bd1f6d6984b7bde396  /usr/local/bin/echoctl' | sha256sum -c - \
    && chmod 0755 /usr/local/bin/echoctl

WORKDIR /work
CMD ["bash"]
