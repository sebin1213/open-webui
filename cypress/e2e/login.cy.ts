describe('Login', () => {
	it('check login', () => {
		cy.login(Cypress.env('email'), Cypress.env('password'));
	});
});
