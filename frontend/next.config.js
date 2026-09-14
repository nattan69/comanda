/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: { ignoreDuringBuilds: true },

  // PROXY d'API (patró d'Estada, aplicat 14/09/2026):
  // les crides a /api/* del NAVEGADOR es reenvien al backend FastAPI del mateix
  // host. Així el front i el backend comparteixen domini públic — sense CORS i,
  // sobretot, sense que el navegador del cambrer intenti cridar el SEU localhost
  // (que era el que trencava el desplegament: els centres no carregaven).
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
