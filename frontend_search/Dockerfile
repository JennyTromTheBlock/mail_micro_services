# Use a Node.js image to build the frontend
FROM node:18 AS frontend

# Set working directory
WORKDIR /app

# Copy the package.json and install dependencies
COPY package*.json ./
RUN npm install

# Copy the rest of the frontend code
COPY . .

# Build the frontend
RUN npm run build

# Expose the port for the frontend
EXPOSE 3000

# Start the frontend directly in production mode
CMD ["node", "./.output/server/index.mjs"]
