interface Registration {
    unregister?(): void;
}
export type Register = (cb: (...args: unknown[]) => void) => Registration | undefined;

/** Subscribe to a SteamClient event. On some Steam builds the method is missing or throws "Unknown method";
 * then this is a no-op instead of an exception. */
export function safeRegister(fn: Register | undefined, cb: (...args: unknown[]) => void): () => void {
    if (typeof fn !== 'function') return () => {};
    try {
        const handle = fn(cb);
        return () => {
            try {
                handle?.unregister?.();
            } catch {
                // nothing to undo
            }
        };
    } catch {
        return () => {};
    }
}
