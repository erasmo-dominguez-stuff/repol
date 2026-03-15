FROM node

RUN apk add --no-cache curl && \
    npm install -g smee-client && \
    npm cache clean --force

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
