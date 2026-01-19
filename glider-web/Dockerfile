FROM node:22-slim

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the production app
RUN npm run build

# Expose the production server port
EXPOSE 3000

# Run the production server
CMD ["node", "build"]
