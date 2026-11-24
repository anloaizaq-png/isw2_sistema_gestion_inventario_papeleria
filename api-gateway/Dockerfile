# =====================================================================
# Dockerfile: gateway-service (Node.js 20 Alpine)
# Microservicio API Gateway y de Identidad - Cotton Cloud Paper
# =====================================================================

FROM node:20-alpine

# Directorio de trabajo
WORKDIR /app

# Variables de entorno por defecto
ENV NODE_ENV=production \
    PORT=8080

# Copiar manifiesto de dependencias e instalar dependencias de producción
# Se utiliza `npm install --omit=dev` para instalar dentro del contenedor sin exigir package-lock.json previo
COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund

# Copiar código fuente y esquemas SQL
COPY src/ ./src/
COPY sql/ ./sql/

# Configurar permisos de usuario no privilegiado
RUN chown -R node:node /app
USER node

# Exponer el puerto del Gateway
EXPOSE 8080

# Healthcheck nativo consultando el endpoint /health
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# Comando de inicio
CMD ["node", "src/server.js"]
