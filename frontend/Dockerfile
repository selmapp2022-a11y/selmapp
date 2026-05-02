# Stage 1: Build the Flutter Web App
FROM ubuntu:24.04 AS build-env

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git unzip xz-utils zip libglu1-mesa ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Setup Flutter (stable channel = latest Dart)
RUN git clone --depth 1 https://github.com/flutter/flutter.git /usr/local/flutter -b stable
ENV PATH="/usr/local/flutter/bin:/usr/local/flutter/bin/cache/dart-sdk/bin:${PATH}"

# Make Flutter ready (downloads engine artifacts)
RUN git config --global --add safe.directory /usr/local/flutter \
    && flutter --disable-analytics \
    && flutter precache --web

WORKDIR /app

# Cache deps separately so code changes don't redownload them
COPY pubspec.yaml pubspec.lock* ./
RUN flutter pub get || true

# Now copy rest of source and resolve again
COPY . .
RUN flutter pub get

# Web app is mounted under /app/ on selmapp.com, so all internal asset
# URLs must include that prefix. DigitalOcean strips the route prefix
# when forwarding, so the container itself still serves at /.
RUN flutter build web --release --pwa-strategy=none --base-href "/app/"

# Stage 2: Serve with nginx, with SPA fallback for client-side routing
FROM nginx:alpine

# Replace default site with one that always falls back to index.html
RUN rm -f /etc/nginx/conf.d/default.conf
COPY --from=build-env /app/build/web /usr/share/nginx/html

RUN cat > /etc/nginx/conf.d/app.conf <<'NGINX_EOF'
server {
    listen 80 default_server;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Long cache for hashed assets, no cache for index/manifest
    location ~* \.(js|css|woff2?|ttf|otf|png|jpg|jpeg|gif|webp|svg|ico|wasm)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;
    }

    location = /index.html {
        add_header Cache-Control "no-store";
    }

    location = /flutter_service_worker.js {
        add_header Cache-Control "no-store";
    }

    # SPA fallback: any unknown route serves index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Health check for DigitalOcean
    location = /healthz {
        access_log off;
        return 200 "ok\n";
        add_header Content-Type text/plain;
    }
}
NGINX_EOF

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
