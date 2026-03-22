// frontend/src/hooks/useAutoScroll.ts
import { useEffect, useRef, useCallback } from 'react';

export function useAutoScroll(deps: unknown[], threshold = 120) {
    const scrollRef = useRef<HTMLDivElement>(null);
    const isNearBottomRef = useRef(true);

    const handleScroll = useCallback(() => {
        const el = scrollRef.current;
        if (!el) return;
        const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
        isNearBottomRef.current = distanceFromBottom <= threshold;
    }, [threshold]);

    useEffect(() => {
        const el = scrollRef.current;
        if (!el) return;
        el.addEventListener('scroll', handleScroll, { passive: true });
        return () => el.removeEventListener('scroll', handleScroll);
    }, [handleScroll]);

    // Only auto-scroll when user is already near the bottom
    // eslint-disable-next-line react-hooks/exhaustive-deps
    useEffect(() => {
        if (!isNearBottomRef.current) return;
        const el = scrollRef.current;
        if (!el) return;
        el.scrollTop = el.scrollHeight;
    }, deps);

    const scrollToBottom = useCallback(() => {
        const el = scrollRef.current;
        if (!el) return;
        el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
        isNearBottomRef.current = true;
    }, []);

    return { scrollRef, scrollToBottom, isNearBottomRef };
}