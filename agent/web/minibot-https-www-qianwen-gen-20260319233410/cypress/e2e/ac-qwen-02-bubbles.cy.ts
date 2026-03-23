/// <reference types="cypress" />

describe('AC-QWEN-02: Message Bubble Styling Validation', () => {
  beforeEach(() => {
    cy.visit('http://127.0.0.1:3000/chat');
  });

  it('should render user and assistant bubbles with correct styling', () => {
    // Simulate a user message
    cy.get('.chat-input').type('Hello, Qwen!{enter}');
    
    // Wait for assistant response (mocked or real)
    cy.get('.message-assistant').should('be.visible');

    // Verify user bubble
    cy.get('.message-user').should($el => {
      const style = getComputedStyle($el[0]);
      expect(style.borderRadius).to.eq('8px');
      expect(style.padding).to.eq('0.5rem 1rem'); // --spacing-sm / --spacing-md
      expect(style.backgroundColor).to.eq('rgb(245, 245, 245)'); // --color-bg-message-user
    });

    // Verify assistant bubble
    cy.get('.message-assistant').should($el => {
      const style = getComputedStyle($el[0]);
      expect(style.borderRadius).to.eq('8px');
      expect(style.padding).to.eq('0.5rem 1rem');
      expect(style.backgroundColor).to.eq('rgb(230, 247, 255)'); // --color-bg-message-assistant
    });
  });
});
