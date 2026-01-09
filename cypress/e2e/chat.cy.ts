// eslint-disable-next-line @typescript-eslint/triple-slash-reference
/// <reference path="../support/index.d.ts" />

// These tests run through the chat flow.
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
	});

	context('Ollama', () => {
		it('user can select a model', () => {
			// Click on the model selector
			cy.findByLabelText('Select a model').click();

			// Select the first model
			cy.findAllByRole('button').filter('[aria-roledescription="model-item"]').first().click();
		});

		it('user can perform text chat', () => {
			// Click on the model selector
			cy.findByLabelText('Select a model').click();

			// Select the first model
			cy.findAllByRole('button').filter('[aria-roledescription="model-item"]').first().click();

			// Type a message
			cy.get('#chat-input').click();
			cy.get('#chat-input').type('Hi, what can you do? A single sentence only please.', {
				force: true
			});

			// Send the message
			cy.get('#send-message-button').click();

			// // User's message should be visible
			cy.get('.chat-user').should('exist');

			// // Wait for the response
			// // .chat-assistant is created after the first token is received
			cy.get('.chat-assistant', { timeout: 10_000 }).should('exist');

			// // Generation Info is created after the stop token is received
			cy.get('.status-description').get('.shimmer', { timeout: 120_000 }).should('not.exist');
		});

		it('user can share chat', () => {
			// Click on the model selector
			cy.get('button[aria-label="Select a model"]').click();

			// Select the first model
			cy.get('button[aria-roledescription="model-item"]').first().click();

			// Type a message
			cy.get('#chat-input').click();
			cy.get('#chat-input').type('Hi, what can you do? A single sentence only please.', {
				force: true
			});

			// Send the message
			cy.get('button[type="submit"]').click();

			// User's message should be visible
			cy.get('.chat-user').should('exist');

			// Wait for the response
			// .chat-assistant is created after the first token is received
			cy.get('.chat-assistant', { timeout: 10_000 }).should('exist');

			// Generation Info is created after the stop token is received
			cy.get('.status-description').get('.shimmer', { timeout: 120_000 }).should('not.exist');

			// spy on requests
			const spy = cy.spy();
			cy.intercept('POST', '/api/v1/chats/**/share', spy);

			// Open context menu
			cy.get('#chat-context-menu-button').click();

			// Click share button
			cy.get('#chat-share-button').click();

			// Check if the share dialog is visible
			cy.get('#copy-and-share-chat-button').should('exist');

			// Click the copy button
			cy.get('#copy-and-share-chat-button').click();
			cy.wrap({}, { timeout: 5_000 }).should(() => {
				// Check if the share request was made
				expect(spy).to.be.callCount(1);
			});
		});

		it('user can perform image chat', () => {
			// Click on the model selector
			cy.findByLabelText('Select a model').click();

			// Select the first model
			cy.findAllByRole('button').filter('[aria-roledescription="model-item"]').first().click();

			// Drag Drop test image file
			cy.get('#chat-container').selectFile('cypress/fixtures/test-img.png', {
				action: 'drag-drop'
			});

			// Write Text
			cy.get('#chat-input').click();
			cy.get('#chat-input').type('사진 내용을 요약해줘', {
				force: true
			});

			// Send the message
			cy.get('#send-message-button').click();

			// // User's message should be visible
			cy.get('.chat-user').should('exist');

			cy.get('.chat-assistant', { timeout: 10_000 }).should('exist');

			// // Generation Info is created after the stop token is received
			cy.get('.status-description').get('.shimmer', { timeout: 120_000 }).should('not.exist');
		});

		it('user can perform file chat', () => {
			// Click on the model selector
			cy.findByLabelText('Select a model').click();

			// Select the first model
			cy.findAllByRole('button').filter('[aria-roledescription="model-item"]').first().click();

			// Drag Drop test pdf file
			cy.get('#chat-container').selectFile('cypress/fixtures/test-img.pdf', {
				action: 'drag-drop'
			});

			// File upload complete
			cy.get('form button').first().find('svg').should('have.class', 'size-5');

			// Write Text
			cy.get('#chat-input').click();
			cy.get('#chat-input').type('파일 내용을 요약해줘', {
				force: true
			});

			// Send the message
			cy.get('#send-message-button').click();

			// User's message should be visible
			cy.get('.chat-user').should('exist');

			cy.get('.chat-assistant', { timeout: 10_000 }).should('exist');

			// // Generation Info is created after the stop token is received
			cy.get('.status-description').get('.shimmer', { timeout: 120_000 }).should('not.exist');
		});
	});
});
