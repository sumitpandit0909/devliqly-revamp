'use strict';

// Read-only actions the website needs without an API token
const PUBLIC_ACTIONS = ['api::article.article.find', 'api::article.article.findOne'];

module.exports = {
  register(/*{ strapi }*/) {},

  // Make published articles readable by the public role, so the site can fetch them anonymously
  async bootstrap({ strapi }) {
    const role = await strapi.db.query('plugin::users-permissions.role').findOne({ where: { type: 'public' } });
    if (!role) return;

    for (const action of PUBLIC_ACTIONS) {
      const existing = await strapi.db.query('plugin::users-permissions.permission').findOne({ where: { action, role: role.id } });
      if (!existing) {
        await strapi.db.query('plugin::users-permissions.permission').create({ data: { action, role: role.id } });
      }
    }
  },
};
