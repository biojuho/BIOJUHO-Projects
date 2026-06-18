# Use Node.js LTS
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./
COPY tsconfig.build.json ./
COPY vite.config.ts ./

# Install dependencies
RUN npm ci

# Copy source code (UI components live under src/components)
COPY src ./src

# Build the widgets (Vite) and server (TypeScript)
# This creates the assets/ directory with built HTML/JS/CSS
RUN npm run build

# Expose the port
EXPOSE 8001

# Set environment variable for port
ENV PORT=8001

# Run as the built-in non-root node user (container-escape hardening)
RUN chown -R node:node /app
USER node

# Start the server
CMD ["node", "dist/server/server.js"]
