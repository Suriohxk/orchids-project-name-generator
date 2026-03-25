/**
 * Map a [0,1] anomaly score to a color suitable for vis-network nodes.
 */
export function scoreToColor(score) {
  if (score >= 0.75) return { background: '#7f1d1d', border: '#ef4444', font: '#fca5a5' }
  if (score >= 0.55) return { background: '#7c2d12', border: '#f97316', font: '#fed7aa' }
  if (score >= 0.35) return { background: '#713f12', border: '#eab308', font: '#fef08a' }
  return { background: '#0f2d1a', border: '#22c55e', font: '#86efac' }
}

export function scoreToTailwind(score) {
  if (score >= 0.75) return 'badge-danger'
  if (score >= 0.55) return 'badge-warn'
  return 'badge-safe'
}

export function scoreLabel(score) {
  if (score >= 0.75) return 'CRITICAL'
  if (score >= 0.55) return 'SUSPICIOUS'
  if (score >= 0.35) return 'ELEVATED'
  return 'BENIGN'
}

export function formatTs(ts) {
  return new Date(ts * 1000).toLocaleTimeString()
}

export function formatNumber(n) {
  if (n === undefined || n === null) return '—'
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return n.toFixed ? n.toFixed(0) : String(n)
}
