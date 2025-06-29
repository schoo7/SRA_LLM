# SRA-LLM Test Environment Dockerfile
# ====================================
# This Dockerfile creates a clean Ubuntu environment to test the
# installation and setup scripts as if on a new computer.
#
# Build command (from the 'github' directory):
#   docker build -t sra-llm-test .
#
# Run command (to get an interactive shell inside the container):
#   docker run -it --rm sra-llm-test

# Use a standard, recent Ubuntu image as the base
FROM ubuntu:22.04

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install essential dependencies for the installer to run
# - python3, pip, venv for the application
# - git to clone repositories (if needed)
# - curl for downloading installers (like NCBI tools)
# - sudo as some scripts might use it
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-pip \
    python3.10-venv \
    git \
    curl \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Create a symbolic link for python3 to point to python3.10
RUN ln -sf /usr/bin/python3.10 /usr/bin/python3

# Set the working directory inside the container
WORKDIR /app

# Copy all the files from the 'github' directory into the container's /app directory
COPY . .

# Give execute permissions to all shell and command scripts
RUN chmod +x *.sh *.command

# Hand over to an interactive bash shell when the container runs.
# From here, the user can manually run the installation scripts.
# For example:
#   root@<container_id>:/app# python3 install_sra_analyzer.py
#   root@<container_id>:/app# ./run_enhanced_web_app.sh
CMD ["/bin/bash"] 