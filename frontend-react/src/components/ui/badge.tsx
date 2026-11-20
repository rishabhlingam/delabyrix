import * as React from "react";
import { cn } from "@/lib/utils";

function Badge({
  className,
  variant = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & {
  variant?: "default" | "outline";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-none border px-2 py-0.5 text-xs font-medium transition-colors",
        variant === "default" &&
          "border-transparent bg-primary text-primary-foreground",
        variant === "outline" && "border-border bg-transparent text-foreground",
        className
      )}
      {...props}
    />
  );
}

export { Badge };
