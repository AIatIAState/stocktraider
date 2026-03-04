import Box from '@mui/material/Box'

// Stock-chart themed loader: a trend line draws itself left-to-right, then fades and replays.
// Uses brand colors (indigo -> teal gradient). No new dependencies - pure SVG + CSS animation.
export function GradientCircularProgress() {
  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg
        width="120"
        height="56"
        viewBox="0 0 100 46"
        aria-label="Loading…"
        overflow="visible"
      >
        <defs>
          <linearGradient id="stock-loader-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#7986CB" />
            <stop offset="100%" stopColor="#00D3AB" />
          </linearGradient>
          <style>{`
            @keyframes stockDraw {
              0%   { stroke-dashoffset: 125; opacity: 1; }
              68%  { stroke-dashoffset: 0;   opacity: 1; }
              85%  { stroke-dashoffset: 0;   opacity: 1; }
              100% { stroke-dashoffset: 0;   opacity: 0; }
            }
            @keyframes dotPop {
              0%, 66%  { opacity: 0; }
              78%, 87% { opacity: 1; }
              100%     { opacity: 0; }
            }
            @keyframes basePulse {
              0%, 100% { opacity: 0.12; }
              50%      { opacity: 0.28; }
            }
          `}</style>
        </defs>

        {/* Baseline axis */}
        <line
          x1="0" y1="42" x2="100" y2="42"
          stroke="#7986CB"
          strokeWidth="1"
          strokeLinecap="round"
          style={{ animation: 'basePulse 2.4s ease-in-out infinite' }}
        />

        {/* Upward trend line — draws itself left to right */}
        <polyline
          points="0,38 15,28 25,33 40,18 55,23 70,8 85,13 100,3"
          fill="none"
          stroke="url(#stock-loader-grad)"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray="125"
          strokeDashoffset="125"
          style={{ animation: 'stockDraw 2.4s ease-in-out infinite' }}
        />

        {/* Peak dot that appears when the line finishes */}
        <circle
          cx="100" cy="3" r="3.5"
          fill="#00D3AB"
          style={{ animation: 'dotPop 2.4s ease-in-out infinite' }}
        />
      </svg>
    </Box>
  )
}
