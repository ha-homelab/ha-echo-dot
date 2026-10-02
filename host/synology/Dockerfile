FROM debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251

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
