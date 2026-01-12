/// <reference types="cypress" />
// eslint-disable-next-line @typescript-eslint/triple-slash-reference
/// <reference path="./index.d.ts" />

import '@testing-library/cypress/add-commands';

const login = (email: string, password: string) => {
	return cy.session(
		email,
		() => {
			localStorage.setItem('locale', 'en-US');
			cy.visit('/auth');

			cy.findByLabelText(/email/i).type(email);
			cy.findByLabelText(/password/i).type(password);
			cy.findByRole('button', { name: /sign in|login|submit/i }).click();
		},
		{
			validate: () => {
				cy.request({
					method: 'GET',
					url: '/api/v1/auths',
					headers: {
						Authorization: 'Bearer ' + localStorage.getItem('token')
					}
				});
			}
		}
	);
};

// const register = (name: string, email: string, password: string) => {
// 	return cy
// 		.request({
// 			method: 'POST',
// 			url: '/api/v1/auths/signup',
// 			body: {
// 				name: name,
// 				email: email,
// 				password: password
// 			},
// 			failOnStatusCode: false
// 		})
// 		.then((response) => {
// 			expect(response.status).to.be.oneOf([200, 400]);
// 		});
// };

// const registerAdmin = () => {
// 	return register(adminUser.name, adminUser.email, adminUser.password);
// };

// const loginAdmin = () => {
// 	return login(adminUser.email, adminUser.password);
// };

Cypress.Commands.add('login', (email, password) => login(email, password));
// Cypress.Commands.add('register', (name, email, password) => register(name, email, password));
// Cypress.Commands.add('registerAdmin', () => registerAdmin());
// Cypress.Commands.add('loginAdmin', () => loginAdmin());
