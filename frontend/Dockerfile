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
RUN flutter build web --release --pwa-strategy=none --base-href "/"

# Stage 2: Serve with nginx, with SPA fallback for client-side routing
FROM nginx:alpine

# Replace default site with one that always falls back to index.html.
# We use a real COPY here because Kaniko (DO's build engine) does NOT
# evaluate bash heredoc bodies inside RUN — it would create an empty
# config file and nginx would have no server block, refusing :80.
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx-app.conf /etc/nginx/conf.d/app.conf
COPY --from=build-env /app/build/web /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
