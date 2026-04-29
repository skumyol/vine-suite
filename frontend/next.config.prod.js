/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    appDir: true,
  },
  output: 'standalone',
  // Base path for production deployment at /vine
  basePath: '/vine',
  // Asset prefix for static files
  assetPrefix: '/vine',
  // Nginx handles API proxying - no rewrites needed
  // Client calls /vine/api/xxx -> nginx -> backend:9002
  trailingSlash: false,
};

module.exports = nextConfig;
