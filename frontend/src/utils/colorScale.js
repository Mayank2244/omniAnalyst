/**
 * OmniRoute Analytics — DCLI Color Scale Utilities
 * Maps DCLI scores to colors for Deck.gl and UI components.
 */

// DCLI → RGBA color for Deck.gl layers
export function dcliToRgba(dcli) {
  if (dcli < 200) return [0, 255, 100, 180]       // Green — free flow
  if (dcli < 1000) return [255, 200, 0, 200]      // Yellow — moderate
  if (dcli < 5000) return [255, 100, 0, 220]      // Orange — heavy
  return [255, 20, 20, 255]                         // Red — gridlock
}

// DCLI → CSS color string for UI elements
export function dcliToColor(dcli) {
  if (dcli < 200) return '#059669'   // Green
  if (dcli < 1000) return '#eab308'  // Yellow
  if (dcli < 5000) return '#ea580c'  // Orange
  return '#dc2626'                    // Red
}

// DCLI → congestion level label
export function dcliToLevel(dcli) {
  if (dcli < 200) return 'free'
  if (dcli < 1000) return 'moderate'
  if (dcli < 5000) return 'heavy'
  return 'gridlock'
}

// Risk level → CSS color
export function riskColor(level) {
  const colors = {
    CRITICAL: '#dc2626',
    HIGH: '#ea580c',
    MEDIUM: '#2563eb',
    LOW: '#059669',
  }
  return colors[level] || '#4f46e5'
}

// Risk level → Deck.gl RGBA
export function riskToRgba(level) {
  const colors = {
    CRITICAL: [220, 38, 38, 200],
    HIGH: [234, 88, 12, 200],
    MEDIUM: [37, 99, 235, 200],
    LOW: [5, 150, 105, 200],
  }
  return colors[level] || [79, 70, 229, 200]
}

// Interpolate between two colors based on a 0-1 value
export function interpolateColor(value, fromColor = [5, 150, 105], toColor = [220, 38, 38]) {
  const v = Math.max(0, Math.min(1, value))
  return [
    Math.round(fromColor[0] + (toColor[0] - fromColor[0]) * v),
    Math.round(fromColor[1] + (toColor[1] - fromColor[1]) * v),
    Math.round(fromColor[2] + (toColor[2] - fromColor[2]) * v),
    200,
  ]
}

// Format currency (INR)
export function formatINR(value) {
  if (value == null) return '₹0'
  return `₹${Math.round(value).toLocaleString('en-IN')}`
}
