const { defineConfig } = require('cypress');

module.exports = defineConfig({
  e2e: {
    baseUrl: 'http://localhost:5000', // Указываем Cypress, где искать наше приложение
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
  },
});