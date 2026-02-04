###############################
# Build frontend
###############################

# install node and npm stuff
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

###############################
# Serve frontend with nginx
###############################

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
# reverse proxy to the FastAPI backend, which is running on port 5000
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
