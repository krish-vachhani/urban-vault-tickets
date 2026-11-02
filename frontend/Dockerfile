# Local development image: runs the Vite dev server with hot reload.
# (Production serves the static `npm run build` output from S3 + CloudFront.)
FROM node:24-alpine

WORKDIR /app

# Install dependencies first so this layer is cached between code changes.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
