FROM alpine:3.19

# Install wget for healthchecks and setup loki user
RUN apk add --no-cache ca-certificates wget su-exec tzdata && \
    adduser -D -H -u 10001 loki && \
    mkdir -p /loki && \
    chown -R loki:loki /loki

# Copy the static loki binary from the official image
COPY --from=grafana/loki:latest /usr/bin/loki /usr/bin/loki

EXPOSE 3100
USER loki
ENTRYPOINT ["/usr/bin/loki"]
