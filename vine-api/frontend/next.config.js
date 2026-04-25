/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    appDir: true,
  },
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/v1/:path*',
      },
      {
        source: '/health/:path*',
        destination: 'http://localhost:8000/health/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
