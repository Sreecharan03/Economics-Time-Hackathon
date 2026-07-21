# Build context is this directory (services/*/Dockerfile use the repo root
# instead, since they read dataset/ files; frontend never touches the
# dataset, it only talks to gateway over HTTP).
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-slim AS run
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/public ./public
COPY --from=build /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json

# Runtime env, not build-time -- the API proxy route (app/api/gateway/) runs
# server-side inside this container and reads this at request time, unlike
# NEXT_PUBLIC_* vars which would need baking in at `next build`. Override
# via docker-compose's environment: for the container-network gateway
# address (e.g. http://gateway:8000).
ENV GATEWAY_INTERNAL_URL=http://localhost:8000

EXPOSE 3000
CMD ["npm", "run", "start"]
