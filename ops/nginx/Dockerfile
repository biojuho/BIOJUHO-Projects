FROM nginx:alpine

# Install mkcert for local dev SSL
RUN apk add --no-cache nss-tools curl bash && \
    curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64" && \
    chmod +x mkcert-v*-linux-amd64 && \
    mv mkcert-v*-linux-amd64 /usr/local/bin/mkcert

# Generate local dev SSL certs
RUN mkdir -p /etc/nginx/ssl && \
    mkcert -install && \
    mkcert -cert-file /etc/nginx/ssl/agriguard.crt -key-file /etc/nginx/ssl/agriguard.key agriguard.local localhost && \
    mkcert -cert-file /etc/nginx/ssl/desci.crt -key-file /etc/nginx/ssl/desci.key desci.local localhost

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
