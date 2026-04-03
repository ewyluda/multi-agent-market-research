import * as React from "react"
import { cva } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--ring)] focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-[var(--primary)] text-[var(--primary-foreground)]",
        secondary: "border-transparent bg-[var(--secondary)] text-[var(--secondary-foreground)]",
        destructive: "border-transparent bg-[var(--destructive)] text-white",
        outline: "text-[var(--card-foreground)]",
        success: "border-transparent bg-[rgba(23,201,100,0.15)] text-[#17c964]",
        warning: "border-transparent bg-[rgba(245,165,36,0.15)] text-[#f5a524]",
        danger: "border-transparent bg-[rgba(243,18,96,0.15)] text-[#f31260]",
      },
    },
    defaultVariants: { variant: "default" },
  }
)

const Badge = React.forwardRef(({ className, variant, ...props }, ref) => (
  <div ref={ref} className={cn(badgeVariants({ variant }), className)} {...props} />
))
Badge.displayName = "Badge"

export { Badge, badgeVariants }
