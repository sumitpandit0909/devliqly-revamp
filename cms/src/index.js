'use strict';

// Read-only actions the website needs without an API token
const PUBLIC_ACTIONS = ['api::article.article.find', 'api::article.article.findOne'];

// Publishing touches several rows at once, so wait for the burst to settle before asking for one rebuild
const REBUILD_DELAY_MS = 15000;

function rebuildTrigger(strapi) {
  const hook = process.env.SITE_DEPLOY_HOOK;
  if (!hook) return () => {};
  let timer;
  return () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      try {
        const res = await fetch(hook, { method: 'POST' });
        strapi.log.info(`Requested a website rebuild (${res.status})`);
      } catch (err) {
        strapi.log.error(`Website rebuild request failed: ${err.message}`);
      }
    }, REBUILD_DELAY_MS);
  };
}

module.exports = {
  register(/*{ strapi }*/) {},

  async bootstrap({ strapi }) {
    // Make published articles readable by the public role, so the site can fetch them anonymously
    const role = await strapi.db.query('plugin::users-permissions.role').findOne({ where: { type: 'public' } });
    if (role) {
      for (const action of PUBLIC_ACTIONS) {
        const existing = await strapi.db.query('plugin::users-permissions.permission').findOne({ where: { action, role: role.id } });
        if (!existing) {
          await strapi.db.query('plugin::users-permissions.permission').create({ data: { action, role: role.id } });
        }
      }
    }

    // The website pre-renders posts, the sitemap and the RSS feed at build time, so rebuild it when articles change
    const rebuild = rebuildTrigger(strapi);
    strapi.db.lifecycles.subscribe({
      models: ['api::article.article'],
      afterCreate: rebuild,
      afterUpdate: rebuild,
      afterDelete: rebuild,
    });
  },
};
