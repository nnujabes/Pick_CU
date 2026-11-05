import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/utils/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-btn border font-mono font-bold tracking-[0.02em] transition-colors disabled:opacity-50",
  {
    variants: {
      variant: {
        lime: "border-lime bg-lime text-lime-ink hover:brightness-105",
        ghost: "border-line bg-transparent text-fg hover:border-muted",
        quiet: "border-transparent bg-transparent font-normal text-muted hover:text-fg",
      },
      size: {
        md: "px-4 py-3 text-sm",
        sm: "px-3 py-2 text-[13px]",
      },
    },
    defaultVariants: { variant: "ghost", size: "md" },
  },
);

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, type, ...props }, ref) => {
    const Component = asChild ? Slot : "button";
    return (
      <Component
        ref={ref}
        type={asChild ? undefined : (type ?? "button")}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
