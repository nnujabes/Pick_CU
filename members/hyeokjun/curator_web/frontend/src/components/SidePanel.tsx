import * as DialogPrimitive from "@radix-ui/react-dialog";
import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { useMedia } from "@/hooks/useMedia";
import { useReturnFocus } from "@/hooks/useReturnFocus";
import { cn } from "@/utils/cn";

export const PANEL_WIDTH = 480;

interface Props {
  open: boolean;
  title: string;
  meta?: string;
  onClose: () => void;
  children: ReactNode;
}

/** 오른쪽에서 밀려 나오는 패널. 휴대폰에서는 아래에서 올라오는 시트가 된다. */
export function SidePanel({ open, title, meta, onClose, children }: Props) {
  const isPhone = useMedia("(max-width: 520px)");
  const hidden = isPhone ? { y: "100%" } : { x: "100%" };
  const onCloseAutoFocus = useReturnFocus(open);

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(next) => !next && onClose()}>
      <AnimatePresence>
        {open && (
          <DialogPrimitive.Portal forceMount>
            <DialogPrimitive.Overlay asChild forceMount>
              <motion.div
                className="fixed inset-0 z-50 bg-black/25"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              />
            </DialogPrimitive.Overlay>
            <DialogPrimitive.Content asChild forceMount aria-describedby={undefined} onCloseAutoFocus={onCloseAutoFocus}>
              <motion.div
                className={cn(
                  "fixed z-50 flex flex-col bg-panel outline-none",
                  isPhone
                    ? "inset-x-0 bottom-0 h-[88dvh] rounded-t-card border-t border-line"
                    : "bottom-0 right-0 top-0 border-l border-line",
                )}
                style={isPhone ? undefined : { width: `min(${PANEL_WIDTH}px, 100vw)` }}
                initial={hidden}
                animate={{ x: 0, y: 0 }}
                exit={hidden}
                transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}
              >
                <div className="flex items-center gap-3 border-b border-line p-6">
                  <DialogPrimitive.Title className="text-xl font-bold tracking-[-0.02em]">{title}</DialogPrimitive.Title>
                  {meta && <span className="tnum font-mono text-[13px] text-muted">{meta}</span>}
                  <DialogPrimitive.Close asChild>
                    <Button size="sm" className="ml-auto">
                      닫기
                    </Button>
                  </DialogPrimitive.Close>
                </div>
                {children}
              </motion.div>
            </DialogPrimitive.Content>
          </DialogPrimitive.Portal>
        )}
      </AnimatePresence>
    </DialogPrimitive.Root>
  );
}
