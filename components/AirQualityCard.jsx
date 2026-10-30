const AQI_LEVELS = [
  { max: 50, label: "Tốt", color: "#16A34A" },
  { max: 100, label: "Trung bình", color: "#EAB308" },
  { max: 150, label: "Không tốt cho nhóm nhạy cảm", color: "#F97316" },
  { max: 200, label: "Không tốt", color: "#DC2626" },
  { max: 300, label: "Rất không tốt", color: "#9333EA" },
  { max: 500, label: "Nguy hại", color: "#854D0E" },
];

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

export default function AirQualityCard({ aqiValue = 0 }) {
  const parsedValue =
    aqiValue === null || aqiValue === "" ? Number.NaN : Number(aqiValue);
  const hasValue = Number.isFinite(parsedValue);
  const value = hasValue ? clamp(parsedValue, 0, 500) : null;
  const level = AQI_LEVELS.find(({ max }) => value !== null && value <= max);
  const progress = value === null ? 0 : (value / 500) * 100;
  const status = level ?? { label: "—", color: "#9CA3AF" };

  return (
    <article className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-sm sm:p-6">
      <header className="flex items-center gap-2.5 text-gray-500">
        <svg
          aria-hidden="true"
          className="h-5 w-5 shrink-0"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
        >
          <path d="M3 7h11a2.5 2.5 0 1 0-2.4-3.2M2 12h16a2.5 2.5 0 1 1-2.4 3.2M4 17h7" />
        </svg>
        <span className="text-sm font-medium">Chất lượng không khí</span>
      </header>

      <div className="py-5 text-center">
        <div className="text-6xl font-semibold leading-none tracking-tight text-black tabular-nums">
          {value === null ? "—" : Math.round(value)}
        </div>
      </div>

      <div
        className="h-1.5 overflow-hidden rounded-full bg-gray-200"
        role="progressbar"
        aria-label="Mức AQI trên thang 0 đến 500"
        aria-valuemin={0}
        aria-valuemax={500}
        aria-valuenow={value ?? 0}
      >
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{
            width: `${progress}%`,
            backgroundColor: status.color,
            backgroundImage:
              "repeating-linear-gradient(135deg, rgba(255,255,255,.35) 0 6px, transparent 6px 12px)",
          }}
        />
      </div>

      <p className="mt-4 text-sm font-semibold" style={{ color: status.color }}>
        {status.label}
      </p>
    </article>
  );
}
