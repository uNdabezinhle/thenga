FROM debian:bookworm-slim AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git unzip xz-utils libglu1-mesa \
    && rm -rf /var/lib/apt/lists/*

ADD https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_3.19.6-stable.tar.xz /tmp/flutter.tar.xz
RUN tar -C /opt -xf /tmp/flutter.tar.xz && rm /tmp/flutter.tar.xz
ENV PATH="/opt/flutter/bin:${PATH}" \
    FLUTTER_HOME="/opt/flutter"
RUN git config --global --add safe.directory /opt/flutter \
    && flutter config --no-analytics --enable-web \
    && flutter precache --web

WORKDIR /src
COPY mobile/pubspec.yaml mobile/pubspec.lock ./
RUN flutter pub get
COPY mobile/ ./
RUN flutter pub get
RUN flutter build web --release --dart-define=REKA_API_BASE=

FROM nginx:alpine

RUN mkdir -p /var/www/static /var/www/media
COPY mobile/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/build/web /usr/share/nginx/html
