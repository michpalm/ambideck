const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** fn, tried up to `tries` times with `delayMs` between tries; rejects with the last error. */
export async function retry<T>(fn: () => Promise<T>, tries: number, delayMs: number,
    sleep: (ms: number) => Promise<void> = wait): Promise<T> {
    let lastError: unknown;
    for (let i = 0; i < tries; i++) {
        if (i > 0) await sleep(delayMs);
        try {
            return await fn();
        } catch (error) {
            lastError = error;
        }
    }
    throw lastError;
}
