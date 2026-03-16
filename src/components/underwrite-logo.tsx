import { cn } from "@/lib/utils";

interface UnderwriteLogoProps {
  className?: string;
  dark?: boolean;
  iconOnly?: boolean;
}

export function UnderwriteLogo({ className, dark = false, iconOnly = false }: UnderwriteLogoProps) {
  const iconColor = dark ? "#9B8FCC" : "#6357A0";
  const textColor = dark ? "#FFFFFF" : "#1A1533";

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {/* Zigzag chart icon */}
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
        <polyline
          points="2,15 7,8 12,13 17,5 20,8"
          stroke={iconColor}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
        <circle cx="2" cy="15" r="1.5" fill={iconColor} />
        <circle cx="7" cy="8" r="1.5" fill={iconColor} />
        <circle cx="12" cy="13" r="1.5" fill={iconColor} />
        <circle cx="17" cy="5" r="1.5" fill={iconColor} />
        <circle cx="20" cy="8" r="1.5" fill={iconColor} />
      </svg>
      {!iconOnly && (
        <span
          style={{
            fontFamily: "var(--font-outfit), sans-serif",
            fontWeight: 800,
            fontSize: "17px",
            letterSpacing: "-0.5px",
            color: textColor,
          }}
        >
          Underwrite
        </span>
      )}
    </div>
  );
}
