const UV_COLORS = [
  { max: 2, color: "#16A34A", label: "Thấp" },
  { max: 5, color: "#EAB308", label: "Trung bình" },
  { max: 7, color: "#F97316", label: "Cao" },
  { max: 10, color: "#DC2626", label: "Rất cao" },
  { max: 12, color: "#9333EA", label: "Cực độ" },
];

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

export default function UVIndexGauge({ uvValue = 0 }) {
  const parsedValue = Number(uvValue);
  const value = Number.isFinite(parsedValue) ? clamp(parsedValue, 0, 12) : 0;
  const { color, label } = UV_COLORS.find(({ max }) => value <= max) ?? UV_COLORS.at(-1);

  const centerX = 120;
  const centerY = 120;
  const radius = 95;
  const arcLength = Math.PI * radius;
  const angle = 180 - (value / 12) * 180;
  const progressOffset = arcLength * (1 - value / 12);

  const tickLabels = [0, 3, 6, 9, 12].map((tick) => {
    const tickAngle = Math.PI - (tick / 12) * Math.PI;
    const labelRadius = radius + 18;
    return {
      value: tick,
      x: centerX + labelRadius * Math.cos(tickAngle),
      y: centerY - labelRadius * Math.sin(tickAngle) + 4,
      x1: centerX + (radius - 8) * Math.cos(tickAngle),
      y1: centerY - (radius - 8) * Math.sin(tickAngle),
      x2: centerX + (radius + 8) * Math.cos(tickAngle),
      y2: centerY - (radius + 8) * Math.sin(tickAngle),
    };
  });

  const displayedValue = Number.isInteger(value) ? value : value.toFixed(1);

  return (
    <div className="flex w-full max-w-[260px] flex-col items-center font-sans">
      <svg
        className="h-auto w-full overflow-visible"
        viewBox="0 0 240 205"
        role="meter"
        aria-label={`UV Index ${displayedValue}, ${label}`}
        aria-valuemin={0}
        aria-valuemax={12}
        aria-valuenow={value}
      >
        <path
          d="M 25 120 A 95 95 0 0 1 215 120"
          fill="none"
          stroke="#E5E7EB"
          strokeWidth="12"
          strokeLinecap="round"
        />
        <path
          className="transition-[stroke-dashoffset] duration-500 ease-out"
          d="M 25 120 A 95 95 0 0 1 215 120"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={arcLength}
          strokeDashoffset={progressOffset}
        />

        {tickLabels.map(({ value: tick, x, y, x1, y1, x2, y2 }) => (
          <g key={tick}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#9CA3AF" strokeWidth="2" />
            <text
              x={x}
              y={y}
              textAnchor="middle"
              className="fill-gray-400 text-[12px]"
            >
              {tick}
            </text>
          </g>
        ))}

        <g
          className="transition-transform duration-500 ease-out"
          style={{
            transformOrigin: `${centerX}px ${centerY}px`,
            transform: `rotate(${180 - angle}deg)`,
          }}
        >
          <path
            d="M 120 120 L 49 120"
            fill="none"
            stroke={color}
            strokeWidth="5"
            strokeLinecap="round"
          />
          <circle cx="120" cy="120" r="7" fill={color} />
          <circle cx="120" cy="120" r="3" fill="white" />
        </g>

        <text
          x="120"
          y="195"
          textAnchor="middle"
          className="fill-gray-950 text-[32px] font-semibold"
        >
          {displayedValue}
        </text>
      </svg>
    </div>
  );
}
