import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default: "bg-[#F0EEE9] text-[#6B6860]",
        green: "bg-[#DCFCE7] text-[#16A34A]",
        red: "bg-[#FEE2E2] text-[#DC2626]",
        accent: "bg-[#FEF3C7] text-[#B8943F]",
        purple: "bg-[#EDE9FE] text-[#6357A0]",
        dark: "bg-[#111111] text-white",
        "strong-buy": "bg-[#16A34A] text-white uppercase tracking-wider",
        "buy": "bg-[#65A30D] text-white uppercase tracking-wider",
        "hold": "bg-[#B8943F] text-white uppercase tracking-wider",
        "pass": "bg-[#DC2626] text-white uppercase tracking-wider",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
