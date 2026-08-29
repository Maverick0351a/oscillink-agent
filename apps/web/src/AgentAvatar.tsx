interface AgentAvatarProps {
  state?: 'foundation-idle'
}

export default function AgentAvatar({ state = 'foundation-idle' }: AgentAvatarProps) {
  return (
    <div className="agent-avatar" data-state={state}>
      <svg
        viewBox="0 0 240 260"
        role="img"
        aria-label="Oscillink Agent avatar, foundation idle"
      >
        <defs>
          <filter id="cyan-glow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <path className="avatar-halo" d="M120 16 210 68v104l-90 52-90-52V68z" />
        <path className="avatar-shell" d="m120 42 65 38v82l-65 38-65-38V80z" />
        <path className="avatar-mask" d="m120 62 48 28-8 67-40 25-40-25-8-67z" />
        <path className="avatar-brow" d="m86 111 26-7M128 104l26 7" />
        <path className="avatar-eye" d="m86 122 26-3-8 12-18-2z" />
        <path className="avatar-eye" d="m154 122-26-3 8 12 18-2z" />
        <path className="avatar-core" d="m120 135 9 15-9 9-9-9z" />
        <path className="avatar-mouth" d="m99 167 21 5 21-5" />
        <path className="avatar-signal" d="M31 86H12M228 86h-19M42 193l-16 10M214 203l-16-10" />
      </svg>
      <span className="avatar-state"><i /> FOUNDATION / IDLE</span>
    </div>
  )
}
