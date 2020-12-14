FROM ubuntu:16.04 

WORKDIR /app
ENV PORT=8080
EXPOSE 8080
RUN apt-get update && apt-get install -y python-pip python-sqlite wget && \
    pip install --upgrade pip && pip install flask werkzeug bcrypt gnupg pyopenssl && \
    cd /app && \
    wget https://github.com/bentasker/LocalChat/archive/v0.0.2.1.tar.gz && \
    tar xf v0.0.2.1.tar.gz && \
    rm -f v0.0.2.1.tar.gz && \
    sed -i "s/host='127.0.0.1'/host='0.0.0.0'/g" LocalChat-0.0.2.1/server/LocalChat.py && \
    useradd -m app && \
    rm -rf /var/lib/apt/lists/*
USER app
CMD ["/app/LocalChat-0.0.2.1/server/LocalChat.py"]
