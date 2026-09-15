/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: { ignoreDuringBuilds: true },

  // PROXY d'API (patró d'Estada, aplicat 14/09/2026):
  // les crides a /api/* del NAVEGADOR es reenvien al backend FastAPI del mateix
  // host. Així el front i el backend comparteixen domini públic — sense CORS i,
  // sobretot, sense que el navegador del cambrer intenti cridar el SEU localhost
  // (que era el que trencava el desplegament: els centres no carregaven).
  //
  // ⚠️ EL PORT ÉS CONFIGURABLE (15/09/2026): al PC de na Maria el backend va al
  // 8000, però al OnePlus el 8000 ja el té Jornals → la demo hi va al 8030.
  // Es sobreescriu amb BACKEND_PORT al .env.local o en compilar.
  async rewrites() {
    const port = process.env.BACKEND_PORT || '8000';
    return [
      {
        source: '/api/:path*',
        destination: `http://localhost:${port}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
