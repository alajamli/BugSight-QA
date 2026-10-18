# BugSight QA - Frontend Dockerfile (React + Vite + Nginx)

FROM node:22-slim AS builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:alpine
COPY --from=builder /build/dist /usr/share/nginx/html
RUN printf 'server {\n\
    listen 80;\n\
    client_max_body_size 200M;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / { try_files $uri $uri/ /index.html; }\n\
    location /api/ { proxy_pass http://backend:5000; proxy_set_header Host $host; client_max_body_size 200M; proxy_read_timeout 300s; }\n\
}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]