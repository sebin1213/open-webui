// load the global Cypress types
/// <reference types="cypress" />
/// <reference types="@testing-library/cypress" />

declare namespace Cypress {
	interface Chainable {
		// login(email: string, password: string): Chainable<Element>;
		login(email: string, password: string): Chainable<null>;
		register(name: string, email: string, password: string): Chainable<Element>;
		registerAdmin(): Chainable<Element>;
		loginAdmin(): Chainable<Element>;
		// uploadTestDocument(suffix: any): Chainable<Element>;
		// deleteTestDocument(suffix: any): Chainable<Element>;
	}
}
