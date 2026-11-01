module.exports = ({ env }) => [
  'strapi::logger',
  'strapi::errors',
  'strapi::security',
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
