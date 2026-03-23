/// <reference types="cypress" />

describe('AC-QWEN-01: White-Blue Theme Validation', () => {
  beforeEach(() => {
    cy.visit('http://127.0.0.1:3000');
  });

  it('should apply global CSS tokens correctly', () => {
    // Verify root-level CSS custom properties
    cy.document().then((doc) => {
      const root = doc.documentElement;
      expect(getComputedStyle(root).getPropertyValue('--color-primary').trim()).to.eq('#1e88e5');
      expect(getComputedStyle(root).getPropertyValue('--color-bg').trim()).to.eq('#ffffff');
      expect(getComputedStyle(root).getPropertyValue('--radius-md').trim()).to.eq('8px');
      expect(getComputedStyle(root).getPropertyValue('--spacing-md').trim()).to.eq('1rem');
    });
  });

  it('should render body with correct background and text color', () => {
    cy.get('body').should('have.css', 'background-color', 'rgb(255, 255, 255)');
    cy.get('body').should('have.css', 'color', 'rgb(31, 41, 55)'); // --color-text-primary
  });

  it('should render primary buttons with correct color', () => {
    cy.get('.chat-submit-btn').should('have.css', 'background-color', 'rgb(30, 136, 229)');
  });
});
