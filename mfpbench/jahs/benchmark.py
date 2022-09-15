from __future__ import annotations

from abc import ABC
from typing import Any

from pathlib import Path

import jahs_bench
from ConfigSpace import Configuration, ConfigurationSpace

from mfpbench.benchmark import Benchmark
from mfpbench.download import DATAROOT
from mfpbench.jahs.config import JAHSConfig
from mfpbench.jahs.priors import (
    CIFAR10_PRIORS,
    COLORECTAL_HISTOLOGY_PRIORS,
    DEFAULT_PRIOR,
    FASHION_MNIST_PRIORS,
)
from mfpbench.jahs.result import JAHSResult
from mfpbench.jahs.spaces import jahs_configspace
from mfpbench.util import rename


class JAHSBenchmark(Benchmark, ABC):
    """Manages access to jahs-bench

    Use one of the concrete classes below to access a specific version:
    * JAHSCifar10
    * JAHSColorectalHistology:
    * JAHSFashionMNIST:
    """

    Config = JAHSConfig
    Result = JAHSResult
    fidelity_name = "epoch"
    fidelity_range = (3, 200, 1)  # TODO: min budget plays a huge role in SH/HB algos

    task: jahs_bench.BenchmarkTasks

    available_priors: dict[str, JAHSConfig]
    _default_prior = DEFAULT_PRIOR

    # Where the data for jahsbench should be located relative to the path given
    _default_download_dir: Path = DATAROOT / "jahs-bench-data"
    _result_renames = {
        "size_MB": "size",
        "FLOPS": "flops",
        "valid-acc": "valid_acc",
        "test-acc": "test_acc",
        "train-acc": "train_acc",
    }
    _result_metrics_active = ("valid-acc", "test-acc", "runtime")

    def __init__(
        self,
        *,
        datadir: str | Path | None = None,
        seed: int | None = None,
        prior: str | Path | JAHSConfig | dict[str, Any] | Configuration | None = None,
    ):
        """
        Parameters
        ----------
        datadir : str | Path | None = None
            The path to where mfpbench stores it data. If left to default (None), will
            use the `_default_download_dir = ./data/jahs-bench-data`.

        seed : int | None = None
            The seed to give this benchmark instance

        prior: str | Path | JAHSConfig | None = None
            The prior to use for the benchmark.
            * if str - A preset
            * if Path - path to a file
            * if dict, Config, Configuration - A config
            * None - Use the default if available
        """
        super().__init__(seed=seed, prior=prior)

        if datadir is None:
            datadir = JAHSBenchmark._default_download_dir

        self.datadir = Path(datadir) if isinstance(datadir, str) else datadir
        if not self.datadir.exists():
            raise FileNotFoundError(
                f"Can't find folder at {self.datadir}, have you run\n"
                f"`python -m mfpbench.download --data-dir {self.datadir.parent}`"
            )

        # Loaded on demand with `@property`
        self._bench: jahs_bench.Benchmark | None = None
        self._configspace = jahs_configspace(name=str(self), seed=self.seed)

        if self.prior is not None:
            self.prior.set_as_default_prior(self._configspace)

    # explicit overwrite
    def load(self) -> None:
        """Pre-load JAHS XGBoost model before querying the first time"""
        # Access the property
        _ = self.bench

    @property
    def bench(self) -> jahs_bench.Benchmark:
        """The underlying benchmark used"""
        if not self._bench:
            self._bench = jahs_bench.Benchmark(
                task=self.task,
                save_dir=self.datadir,
                download=False,
                metrics=self._result_metrics_active,
            )

        return self._bench

    @property
    def space(self) -> ConfigurationSpace:
        """The ConfigurationSpace for this benchmark"""
        return self._configspace

    def query(
        self,
        config: JAHSConfig | dict[str, Any] | Configuration,
        at: int | None = None,
    ) -> JAHSResult:
        """Query the results for a config

        Parameters
        ----------
        config : JAHSConfig | dict[str, Any] | Configuration
            The config to query

        at : int | None = None
            The epoch at which to query at, defaults to max (200) if left as None

        Returns
        -------
        JAHSResult
            The result for the config at the given epoch
        """
        at = at if at is not None else self.end
        assert self.start <= at <= self.end

        if isinstance(config, (Configuration, dict)):
            config = self.Config.from_dict(config)

        assert isinstance(config, self.Config)

        query = config.dict()

        results = self.bench.__call__(query, nepochs=at)
        result = results[at]

        return self.Result.from_dict(
            config=config,
            result=rename(result, keys=self._result_renames),
            fidelity=at,
        )

    def trajectory(
        self,
        config: JAHSConfig | dict[str, Any] | Configuration,
        *,
        frm: int | None = None,
        to: int | None = None,
        step: int | None = None,
    ) -> list[JAHSResult]:
        """Query the trajectory of a config as it ranges over a fidelity

        Parameters
        ----------
        config : JAHSConfig | dict[str, Any] | Configuration
            The config to query

        frm: int | None = None
            Start of the curve, defaults to the minimum fidelity (1)

        to: int | None = None
            End of the curve, defaults to the maximum fidelity (200)

        step: int | None = None
            Step size, defaults to benchmark standard (1 for epoch)

        Returns
        -------
        list[JAHSResult]
            The results over that trajectory
        """
        to = to if to is not None else self.end

        if isinstance(config, (Configuration, dict)):
            config = self.Config.from_dict(config)

        assert isinstance(config, self.Config)

        query = config.dict()

        try:
            results = self.bench.__call__(query, nepochs=to, full_trajectory=True)
        except TypeError:
            # See: https://github.com/automl/jahs_bench_201/issues/5
            results = {
                f: self.bench.__call__(query, nepochs=f)[f]
                for f in self.iter_fidelities(frm=frm, to=to, step=step)
            }

        return [
            self.Result.from_dict(
                config=config,
                fidelity=i,
                result=rename(results[i], keys=self._result_renames),
            )
            for i in self.iter_fidelities(frm=frm, to=to, step=step)
        ]

    def __repr__(self) -> str:
        name = self.__class__.__name__
        paramstr = f"(seed={self.seed}, prior={self.prior})"
        return f"{name}({paramstr})"


class JAHSCifar10(JAHSBenchmark):
    available_priors = CIFAR10_PRIORS
    task = jahs_bench.BenchmarkTasks.CIFAR10


class JAHSColorectalHistology(JAHSBenchmark):
    available_priors = COLORECTAL_HISTOLOGY_PRIORS
    task = jahs_bench.BenchmarkTasks.ColorectalHistology


class JAHSFashionMNIST(JAHSBenchmark):
    available_priors = FASHION_MNIST_PRIORS
    task = jahs_bench.BenchmarkTasks.FashionMNIST
