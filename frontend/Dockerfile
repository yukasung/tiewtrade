# syntax=docker/dockerfile:1
FROM node:22-slim AS base

WORKDIR /app
ENV CI=1

# ติดตั้ง dependency ก่อนคัดลอกโค้ด เพื่อให้ชั้น cache ใช้ซ้ำได้
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
