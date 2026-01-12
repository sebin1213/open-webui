// eslint-disable-next-line @typescript-eslint/triple-slash-reference
// <reference path="../support/index.d.ts" />

// These tests run through the various settings pages, ensuring that the user can interact with them as expected
describe('Settings', () => {
	// Wait for 2 seconds after all tests to fix an issue with Cypress's video recording missing the last few frames
	after(() => {
		// eslint-disable-next-line cypress/no-unnecessary-waiting
		cy.wait(2000);
	});

	beforeEach(() => {
		// Login as the admin user
		cy.login(Cypress.env('email'), Cypress.env('password'));
		// Visit the home page
		cy.visit('/');

		// close update modal
		cy.get('.modal-footer', { timeout: 10000 })
			.should('be.visible')
			.find('.primary-button')
			.click();

		// Click on the user profile
		cy.findAllByRole('button').filter('[data-menu-trigger]').eq(1).click();

		// Click on the settings link
		cy.get('div[role="menuitem"]').eq(0).click();
	});

	context('General', () => {
		it('user can open the General modal and hit save', () => {
			cy.get('button').contains('General').click();
			cy.get('button').contains('Save').click();
		});
	});

	context('Interface', () => {
		it('user can open the Interface modal and hit save', () => {
			cy.get('button').contains('Interface').click();
			cy.get('button').contains('Save').click();
		});
	});

	context('Account', () => {
		it('user can open the Account modal and hit save', () => {
			cy.get('button').contains('Account').click();
			cy.get('button').contains('Save').click();
		});
	});

	context('About', () => {
		it('user can open the About modal', () => {
			cy.get('button').contains('About').click();
		});
	});
});
