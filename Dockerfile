# Use Ubuntu as base image
FROM ubuntu:24.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
  python3 \
  python3-pip \
  && apt-get clean

RUN python3 --version
RUN pip3 --version

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip3 install -r requirements.txt  --break-system-packages

# Open port
EXPOSE 5000

# Run app.py when the container launches
CMD ["python3", "app.py"]
