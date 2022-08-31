from __future__ import annotations

from typing import Any, Iterator, List, Mapping, Sequence, TypeVar, Union

from itertools import chain

import numpy as np
from typing_extensions import Literal

from mfpbench.config import Config
from mfpbench.result import Result
from mfpbench.stats import rank_correlation
from mfpbench.util import intersection

C = TypeVar("C", bound=Config)
R = TypeVar("R", bound=Result)
F = TypeVar("F", int, float)

SENTINEL = object()


# This is a mapping from a
#   Config -> All results for the config over a list of fidelities
#   Fidelity -> All results for that fidelity
class ResultFrame(Mapping[Union[C, F], List[R]]):
    def __init__(self):
        # This lets us quickly index from a config to its registered results
        # We take this to be the rows and __len__
        self._ctor: dict[C, list[R]] = {}

        # This lets us quickly go from a fidelity to its registered results
        # This is akin to the columns
        self._ftor: dict[F, list[R]] = {}

        # This is an ordering for when a config result was added
        self._result_order: list[R] = []

    def __getitem__(self, key: C | F) -> list[R]:
        if isinstance(key, (int, float)):
            return self._ftor[key]
        elif isinstance(key, Config):
            return self._ctor[key]
        else:
            return KeyError(key)

    def __iter__(self) -> Iterator[C]:
        yield from iter(self._ctor)

    def __len__(self) -> int:
        return len(self._ctor)

    def add(self, result: R) -> None:
        """Add a result to the frame"""
        f = result.fidelity
        c = result.config

        if c in self._ctor:
            self._ctor[c].append(result)
        else:
            self._ctor[c] = [result]

        if f in self._ftor:
            self._ftor[f].append(result)
        else:
            self._ftor[f] = [result]

        self._result_order.append(result)

    def __contains__(self, key: C | F | Any) -> bool:
        if isinstance(key, (int, float)):
            return key in self._ftor
        elif isinstance(key, Config):
            return key in self._ctor
        else:
            return False

    @property
    def fidelities(self) -> Iterator[F]:
        yield from iter(self._ftor)

    @property
    def configs(self) -> Iterator[C]:
        yield from iter(self._ctor)

    @property
    def results(self) -> Iterator[R]:
        yield from iter(self._result_order)

    def correlations(
        self,
        at: Sequence[F] | None = None,
        *,
        method: Literal["spearman"] = "spearman",
    ) -> np.ndarray:
        """Get the correlation ranksing between stored results

        To calculate the correlations, we select all configs that are present in each
        selected fidelity.

        Parameters
        ----------
        at: Sequence[F] | None = None
            The fidelities to get correlations between, defaults to all of them

        method: "spearman" = "spearman"
            The method to calculate correlations with

        Returns
        -------
        np.ndarray[at, at]
            The correlation matrix with one row/column per fidelity
        """
        if len(self) == 0:
            raise RuntimeError("Must evaluate at two fidelities at least")
        if len(self._ftor) <= 1:
            raise ValueError(f"Only one fidelity {list(self._ftor)} evaluated")

        if at is None:
            at = list(self._ftor.keys())

        # We get the intersection of configs that are found at all fidelity values
        # {a, b, c}
        common = {r.config for r in self._result_order}

        # Let's assign them all a number
        # {a: 1, b: 2, c: 3}
        assigned = {c: i for i, c in enumerate(common)}

        # Get the selected_fidelities
        selected = {f: self._ftor[f] for f in at}

        # Next we collect only the common configs for each fidelity:
        # Collecting both their error and their assgined number while sorting them by
        # their error
        # {
        #   1: [(b: small, 2), (a: big,   1), (c: Huge, 3)],
        #   2: [(b: tiny,  2), (a: small, 1), (c: big,  3)],
        #   3: [(a: small, 1), (b: big,   2), (c: HUGE, 3)],
        # }
        values = {
            f: sorted((r.error, assigned[r.config]) for r in results)
            for f, results in selected.items()
        }

        # Next we just extract out the orderings and stick it in a numpy array
        values = {f: [num for _, num in error_nums] for f, error_nums in values.items()}
        x = np.asarray([nums for _, nums in values.items()])

        return rank_correlation(x, method=method)
