# Stage 1: Build the Flutter Web App
FROM ubuntu:latest AS build-env

# Install dependencies
RUN apt-get update && apt-get install -y curl git unzip xz-utils zip libglu1-mesa

# Setup Flutter
RUN git clone https://github.com/flutter/flutter.git /usr/local/flutter -b stable
ENV PATH="/usr/local/flutter/bin:/usr/local/flutter/bin/cache/dart-sdk/bin:${PATH}"
RUN flutter doctor -v

# Copy files
WORKDIR /app
COPY . .

# Build Web
RUN flutter pub get
RUN flutter build web --release --pwa-strategy=none

# Stage 2: Serve with Nginx
FROM nginx:alpine
COPY --from=build-env /app/build/web /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]