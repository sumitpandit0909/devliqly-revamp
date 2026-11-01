module.exports = ({ env }) => ({
  host: env('HOST', '0.0.0.0'),
  port: env.int('PORT', 1337),
  // Public address of this CMS, e.g. https://blog.devliqly.in. Needed behind a proxy so admin links and uploads resolve.
  url: env('PUBLIC_URL', ''),
  proxy: env.bool('IS_PROXIED', Boolean(env('PUBLIC_URL'))),
  app: {
    keys: env.array('APP_KEYS'),
  },
  webhooks: {
    populateRelations: env.bool('WEBHOOKS_POPULATE_RELATIONS', false),
  },
});
