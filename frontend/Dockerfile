# Build stage
FROM node:20-alpine AS builder

# Install pnpm
RUN npm install -g pnpm

WORKDIR /app

# Copy package files
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy source code
COPY . .

# Use production config for build
RUN cp next.config.prod.js next.config.js

# Set base path for production build
ENV NEXT_PUBLIC_BASE_PATH=/vine

# Build the application
RUN pnpm build

# Production stage
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Copy built assets
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
# Base path for production deployment
ENV NEXT_PUBLIC_BASE_PATH=/vine

CMD ["node", "server.js"]
