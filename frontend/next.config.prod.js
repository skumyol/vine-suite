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
      // Proxy API calls to backend (Docker network: api:8081)
      {
        source: '/api/v1/:path*',
        destination: 'http://api:8081/api/v1/:path*',
      },
      // Proxy health checks to backend
      {
        source: '/health',
        destination: 'http://api:8081/health',
      },
      {
        source: '/health/:path*',
        destination: 'http://api:8081/health/:path*',
      },
    ];
  },
  // Ensure trailing slashes match nginx expectations
  trailingSlash: false,
};

module.exports = nextConfig;
