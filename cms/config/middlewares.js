module.exports = ({ env }) => [
  'strapi::logger',
  'strapi::errors',
  {
    // Let the admin preview images stored in R2
    name: 'strapi::security',
    config: {
      contentSecurityPolicy: {
        useDefaults: true,
        directives: {
          'connect-src': ["'self'", 'https:'],
          'img-src': ["'self'", 'data:', 'blob:', 'market-assets.strapi.io', env('R2_PUBLIC_URL', '')].filter(Boolean),
          'media-src': ["'self'", 'data:', 'blob:', 'market-assets.strapi.io', env('R2_PUBLIC_URL', '')].filter(Boolean),
          upgradeInsecureRequests: null,
        },
      },
    },
  },
  {
    // Only the website (and local dev) may call the API from a browser
    name: 'strapi::cors',
    config: {
      origin: env.array('CORS_ORIGINS', ['https://www.devliqly.in', 'https://devliqly.in', 'http://localhost:5173', 'http://localhost:4173']),
    },
  },
  'strapi::poweredBy',
  'strapi::query',
  'strapi::body',
  'strapi::session',
  'strapi::favicon',
  'strapi::public',
];
