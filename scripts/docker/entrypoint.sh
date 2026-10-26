#!/usr/bin/env sh
# 컨테이너 공통 진입점. APP_ENV=prod인데 SYSTEM_TOKEN이 JWT가 아니면(dev.sys는 prod에서 막힌다) sys 계정 JWT를 발급해 쓴다.
# JWT_SECRET이 backend와 같아야 하므로 .env 값을 같이 쓴다. DB에 sys 계정이 있어야 해서 db_init 뒤에 뜨는 서비스에서만 의미가 있다.
set -e
case "${APP_ENV:-dev}:${SYSTEM_TOKEN:-}" in
  prod:eyJ*) ;;
  prod:*) SYSTEM_TOKEN="$(python -m apps.backend.auth)" && export SYSTEM_TOKEN ;;
esac
exec "$@"
