import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ShieldCheck, Loader, CheckCircle, AlertCircle, Play } from 'lucide-react';
import { submitVerification, scanVerification, checkArchitecture, scoreVerification, getAuditTrail } from './api';

export default function Dashboard() {
  const [repoUrl, setRepoUrl] = useState('');
  const [prNumber, setPrNumber] = useState('');
  
  const [isVerifying, setIsVerifying] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [error, setError] = useState(null);
  
  const [result, setResult] = useState(null);

  const steps = [
    'Ingesting Pull Request',
    'Scanning Negative-Space',
    'Checking Architecture Fit',
    'Calculating Confidence Score',
    'Fetching Audit Trail'
  ];

  const handleVerify = async (e) => {
    e.preventDefault();
    if (!repoUrl || !prNumber) return;
    
    setIsVerifying(true);
    setError(null);
    setResult(null);
    setCurrentStep(0);
    
    try {
      // Step 1: Submit
      const submitRes = await submitVerification(repoUrl, prNumber);
      const runId = submitRes.runId;
      setCurrentStep(1);
      
      // Step 2: Scan
      const scanRes = await scanVerification(runId);
      setCurrentStep(2);
      
      // Step 3: Architecture
      const archRes = await checkArchitecture(runId);
      setCurrentStep(3);
      
      // Step 4: Score
      const scoreRes = await scoreVerification(runId);
      setCurrentStep(4);
      
      // Step 5: Audit
      const auditRes = await getAuditTrail(runId);
      setCurrentStep(5);
      
      setResult({
        runId,
        score: scoreRes.score,
        explanation: scoreRes.explanation,
        breakdown: scoreRes.breakdown,
        findings: scanRes.findings || [],
        architectureFindings: archRes.findings || [],
        auditTrail: auditRes.auditTrail || []
      });
      
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'An error occurred during verification');
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="container">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
        <h1 className="title">ASEA Verification Dashboard</h1>
        <p className="subtitle">Agent-Agnostic Verification & Trust Layer for AI-Written Code</p>
      </motion.div>

      <div className="grid grid-2">
        {/* Left Column: Input Form */}
        <motion.div className="glass-panel" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
          <h2>Verify Code</h2>
          <form onSubmit={handleVerify}>
            <div className="form-group">
              <label className="form-label">Repository URL</label>
              <input
                type="url"
                className="form-input"
                placeholder="https://github.com/owner/repo"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                required
                disabled={isVerifying}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Pull Request Number</label>
              <input
                type="number"
                className="form-input"
                placeholder="42"
                value={prNumber}
                onChange={(e) => setPrNumber(e.target.value)}
                required
                disabled={isVerifying}
              />
            </div>
            <button type="submit" className="btn" disabled={isVerifying || !repoUrl || !prNumber}>
              {isVerifying ? (
                <><Loader className="spinner" size={18} /> Verifying...</>
              ) : (
                <><Play size={18} /> Run Verification</>
              )}
            </button>
          </form>

          {error && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="error-message" style={{ marginTop: '1rem' }}>
              <AlertCircle size={18} style={{ display: 'inline', marginRight: '0.5rem', verticalAlign: 'middle' }} />
              {error}
            </motion.div>
          )}

          {isVerifying && (
            <div className="loading-steps">
              {steps.map((step, idx) => {
                let status = 'pending';
                if (currentStep > idx) status = 'done';
                if (currentStep === idx) status = 'active';
                return (
                  <div key={idx} className={`loading-step ${status}`}>
                    {status === 'done' ? <CheckCircle size={16} /> : (status === 'active' ? <Loader className="spinner" size={16} /> : <div style={{width:16,height:16,borderRadius:'50%',border:'1px solid var(--text-secondary)'}} />)}
                    <span>{step}</span>
                  </div>
                );
              })}
            </div>
          )}
        </motion.div>

        {/* Right Column: Results */}
        {result && (
          <motion.div className="glass-panel" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
            <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <ShieldCheck color="var(--severity-info)" /> Verification Results
            </h2>
            
            <div className="score-container" style={{ '--score': result.score }}>
              <div className="score-circle">
                <span className="score-value">{result.score}</span>
              </div>
              <div style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>Confidence Score</div>
            </div>
            
            <p style={{ textAlign: 'center', fontSize: '0.9rem', marginBottom: '2rem' }}>{result.explanation}</p>
            
            <div className="findings-list">
              <h3>Findings Breakdown</h3>
              {result.breakdown && result.breakdown.length === 0 && (
                <div className="finding-card" style={{ textAlign: 'center', color: 'var(--severity-info)' }}>
                  No issues found! Perfect score.
                </div>
              )}
              {result.breakdown && result.breakdown.map((item, idx) => (
                <div key={idx} className="finding-card">
                  <div className="finding-header">
                    <span className="finding-title">{item.category}</span>
                    <span className={`status-pill severity-${item.severity}`}>{item.severity}</span>
                  </div>
                  <div className="finding-desc">{item.description}</div>
                  <div className="finding-evidence">{item.reason || item.evidence}</div>
                  <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Source: {item.source} (Penalty: -{item.deduction})</div>
                </div>
              ))}
            </div>

          </motion.div>
        )}
      </div>

      {/* Audit Trail Row */}
      {result && result.auditTrail && (
        <motion.div className="glass-panel" style={{ marginTop: '2rem' }} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <h2>Audit Trail</h2>
          <div className="audit-timeline">
            {result.auditTrail.map((log) => (
              <div key={log.id} className="audit-item">
                <div className="audit-time">{new Date(log.timestamp).toLocaleString()}</div>
                <div className="audit-event">
                  {log.event} <span className={`audit-status ${log.status}`}>{log.status}</span>
                </div>
                {log.details && (
                  <pre className="finding-evidence" style={{ marginTop: '0.5rem' }}>
                    {JSON.stringify(log.details, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}
