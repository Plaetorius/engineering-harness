"""Hard wall-clock limit for hostile-input tests: a regex that backtracks badly fails the test instead of hanging the suite."""
import signal
from contextlib import contextmanager


@contextmanager
def timebox(seconds):
    def expired(signum, frame):
        raise AssertionError(f"still running after {seconds}s: super-linear (ReDoS) behaviour on hostile input")
    old = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
