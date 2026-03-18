import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    Brain,
    Search,
    Database,
    CheckCircle2,
    ChevronDown,
    ChevronUp,
    Clock,
    AlertCircle,
    Loader2,
} from "lucide-react";

export type ThoughtStep = {
    id: string;
    type: "thought" | "tool_start" | "tool_end" | "error";
    message: string;
    icon?: "brain" | "search" | "database" | "check" | "error";
    tool?: string;
    agent?: string;
    elapsed?: number;
    status: "active" | "done" | "error";
    subItems?: string[];
};

interface ThoughtTraceProps {
    steps: ThoughtStep[];
    isStreaming: boolean;
    totalElapsed?: number;
    isCollapsed?: boolean;
    onToggleCollapse?: () => void;
}

const ICONS = {
    brain: Brain,
    search: Search,
    database: Database,
    check: CheckCircle2,
    error: AlertCircle,
};

function StepIcon({ icon, status }: { icon?: string; status: ThoughtStep["status"] }) {
    if (status === "done") {
        return (
            <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="w-5 h-5 rounded-full bg-emerald-500/20 flex items-center justify-center flex-shrink-0"
            >
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            </motion.div>
        );
    }

    if (status === "error") {
        return (
            <div className="w-5 h-5 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0">
                <AlertCircle className="w-3.5 h-3.5 text-red-400" />
            </div>
        );
    }

    // Active — pulsing blue dot
    return (
        <div className="relative flex-shrink-0 w-5 h-5 flex items-center justify-center">
            <motion.div
                className="absolute w-5 h-5 rounded-full bg-blue-500/20"
                animate={{ scale: [1, 1.5, 1], opacity: [0.7, 0, 0.7] }}
                transition={{ duration: 1.4, repeat: Infinity }}
            />
            <div className="w-2.5 h-2.5 rounded-full bg-blue-400 relative z-10" />
        </div>
    );
}

function LiveTimer({ isStreaming, totalElapsed }: { isStreaming: boolean; totalElapsed?: number }) {
    const [elapsed, setElapsed] = useState(0);
    const startRef = useRef(Date.now());

    useEffect(() => {
        if (!isStreaming) return;
        startRef.current = Date.now();
        const interval = setInterval(() => {
            setElapsed((Date.now() - startRef.current) / 1000);
        }, 100);
        return () => clearInterval(interval);
    }, [isStreaming]);

    const display = isStreaming ? elapsed : (totalElapsed ?? elapsed);

    return (
        <span className="ml-auto flex items-center gap-1 text-xs text-white/30 mr-1">
            <Clock className="w-3 h-3" />
            {display.toFixed(1)}s
        </span>
    );
}

export function ThoughtTrace({
    steps,
    isStreaming,
    totalElapsed,
    isCollapsed = false,
    onToggleCollapse,
}: ThoughtTraceProps) {
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (isStreaming && bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [steps, isStreaming]);

    if (steps.length === 0) return null;

    return (
        <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-4 rounded-xl border border-white/[0.06] bg-white/[0.03] overflow-hidden"
        >
            {/* Header */}
            <button
                onClick={onToggleCollapse}
                className="w-full flex items-center gap-2.5 px-4 py-3 hover:bg-white/[0.04] transition-colors"
            >
                <motion.div
                    animate={isStreaming ? { rotate: 360 } : { rotate: 0 }}
                    transition={isStreaming ? { duration: 2, repeat: Infinity, ease: "linear" } : {}}
                >
                    <Brain className="w-4 h-4 text-blue-400" />
                </motion.div>

                <span className="text-sm font-medium text-white/80">
                    {isStreaming ? "Thinking…" : "Thought trace"}
                </span>

                <LiveTimer isStreaming={isStreaming} totalElapsed={totalElapsed} />

                {isCollapsed ? (
                    <ChevronDown className="w-4 h-4 text-white/30" />
                ) : (
                    <ChevronUp className="w-4 h-4 text-white/30" />
                )}
            </button>

            {/* Timeline */}
            <AnimatePresence>
                {!isCollapsed && (
                    <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: "auto" }}
                        exit={{ height: 0 }}
                        className="overflow-hidden"
                    >
                        <div className="px-4 pb-4 pt-1 space-y-0">
                            {steps.map((step, i) => (
                                <motion.div
                                    key={step.id}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ duration: 0.25 }}
                                    className="flex gap-3"
                                >
                                    {/* Vertical connector */}
                                    <div className="flex flex-col items-center">
                                        <StepIcon icon={step.icon} status={step.status} />
                                        {i < steps.length - 1 && (
                                            <div className="w-px flex-1 my-1 bg-white/[0.06]" />
                                        )}
                                    </div>

                                    {/* Content */}
                                    <div className="flex-1 pb-3 min-w-0">
                                        <p className={`text-sm leading-5 ${step.status === "active"
                                            ? "text-white/90"
                                            : step.status === "error"
                                                ? "text-red-400"
                                                : "text-white/50"
                                            }`}>
                                            {step.message}
                                        </p>

                                        {/* Sub-items (e.g. "Database: Technicals Data") */}
                                        {step.subItems && step.subItems.length > 0 && (
                                            <div className="mt-1.5 flex flex-wrap gap-1.5">
                                                {step.subItems.map((sub, si) => (
                                                    <span
                                                        key={si}
                                                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md 
                                       bg-white/[0.06] border border-white/[0.08] 
                                       text-xs text-white/50"
                                                    >
                                                        <Database className="w-3 h-3" />
                                                        {sub}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </motion.div>
                            ))}
                            <div ref={bottomRef} />
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
}