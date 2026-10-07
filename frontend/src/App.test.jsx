import { render, screen } from '@testing-library/react';
import App from './App';
import { expect, test } from 'vitest';

test('renders ASEA Authentication form', () => {
  render(<App />);
  const heading = screen.getByText(/ASEA Authentication/i);
  expect(heading).toBeInTheDocument();
  
  const loginButton = screen.getByRole('button', { name: /login/i });
  expect(loginButton).toBeInTheDocument();
  
  const usernameInput = screen.getByLabelText(/Username/i);
  expect(usernameInput).toBeInTheDocument();
});
