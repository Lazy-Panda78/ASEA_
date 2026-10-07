import React, { useState, useEffect } from 'react';
import Dashboard from './Dashboard';
import { login as apiLogin } from './api';
import { Shield, Lock, AlertCircle } from 'lucide-react';
import { motion } from 'framer-motion';
import './index.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('asea_token');
    if (token) {
      setIsAuthenticated(true);
    }
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    try {
      await apiLogin(username, password);
      setIsAuthenticated(true);
    } catch (err) {
      setError('Invalid username or password.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('asea_token');
    setIsAuthenticated(false);
  };

  if (isAuthenticated) {
    return (
      <div>
        <div style={{ position: 'absolute', top: '1rem', right: '1rem', zIndex: 10 }}>
          <button className="btn" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }} onClick={handleLogout}>
            Logout
          </button>
        </div>
        <Dashboard />
      </div>
    );
  }

  return (
    <div className="auth-wrapper">
      <motion.div className="glass-panel auth-panel" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <Shield size={48} color="var(--accent-blue)" style={{ marginBottom: '1rem' }} />
          <h2>ASEA Authentication</h2>
          <p className="subtitle" style={{ margin: 0 }}>Please log in to continue</p>
        </div>
        
        <form onSubmit={handleLogin}>
          <div className="form-group">
            <label htmlFor="username" className="form-label">Username</label>
            <input
              id="username"
              type="text"
              className="form-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="password" className="form-label">Password</label>
            <input
              id="password"
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="btn" disabled={isLoading || !username || !password}>
            {isLoading ? 'Authenticating...' : <><Lock size={18} /> Login</>}
          </button>
        </form>
        
        {error && (
          <div className="error-message" style={{ marginTop: '1rem' }}>
            <AlertCircle size={16} style={{ display: 'inline', marginRight: '0.5rem', verticalAlign: 'middle' }} />
            {error}
          </div>
        )}
      </motion.div>
    </div>
  );
}

export default App;
