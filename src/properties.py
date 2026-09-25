from contextlib import contextmanager
import sys


@contextmanager
def safe_interrupt_handler(on_interrupt=None):
    """
    Context manager that catches Ctrl+C inside its block,
    runs a cleanup callback if provided, and exits cleanly.
    """
    try:
        yield
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user (Ctrl+C). Saving progress...")
        if callable(on_interrupt):
            on_interrupt()
        print("[+] Progress saved. Exiting gracefully.")
        sys.exit(0)
