import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline" | "ghost" | "destructive";
  size?: "default" | "sm" | "lg";
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { className, variant = "default", size = "default", asChild = false, ...props },
    ref
  ) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(
          "inline-flex items-center justify-center rounded-none font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
          variant === "default" &&
            "bg-[#0f62fe] text-white hover:bg-[#0353e9]",
          variant === "outline" &&
            "border border-border bg-transparent hover:bg-accent hover:text-accent-foreground",
          variant === "ghost" &&
            "bg-transparent hover:bg-[#edf5ff] hover:text-[#0043ce] text-[#0f62fe]",
          variant === "destructive" &&
            "border border-[#da1e28] bg-transparent text-[#da1e28] hover:bg-[#da1e28] hover:text-white",
          size === "default" && "h-10 px-4 py-2 text-sm",
          size === "sm" && "h-8 px-3 py-1 text-xs",
          size === "lg" && "h-11 px-8 text-base",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button };
