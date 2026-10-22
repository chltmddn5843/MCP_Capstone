# 1단계: Vite 빌드 → 2단계: nginx가 정적 파일을 서빙하고 /api/* 를 백엔드로 프록시한다.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# nginx 이미지는 /etc/nginx/templates/*.template 의 ${VAR}를 환경변수로 치환해 conf.d에 놓는다.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
ENV BACKEND_UPSTREAM=http://backend:8000
EXPOSE 80
