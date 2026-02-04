# The official Node.js image
FROM node:24-alpine

# Set the working directory
WORKDIR /app

# Copy package manager files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install

# Optional API base for build-time configuration
ARG VITE_API_BASE
ENV VITE_API_BASE=$VITE_API_BASE

# Copy the rest of the source code
COPY . .

# Build the Vite project
RUN npm run build

# Expose the port
EXPOSE 8080

# Serve the built app
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "8080"]
