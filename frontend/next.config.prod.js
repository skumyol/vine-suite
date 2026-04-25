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
  async rewrites() {
    return [
      // API calls go to /vine/api/ which nginx proxies to backend
      {
        source: '/api/:path*',
        destination: '/api/:path*',
      },
      // Health checks
      {
        source: '/health/:path*',
        destination: '/health/:path*',
      },
    ];
  },
  // Ensure trailing slashes match nginx expectations
  trailingSlash: false,
};

module.exports = nextConfig;
