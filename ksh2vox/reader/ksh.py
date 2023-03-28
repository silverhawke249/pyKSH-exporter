import fractions
import io


def read_ksh(f: io.TextIOBase) -> None:
    bpms: list[float] = []
    time_sigs: list[fractions.Fraction] = []

    for line in f:

