from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, ClassVar, Mapping, Sequence, TypeVar
from typing_extensions import override

import yahpo_gym

from mfpbench.benchmark import Benchmark
from mfpbench.setup_benchmark import YAHPOSource
from mfpbench.util import remove_hyperparameter
from mfpbench.yahpo.config import YAHPOConfig
from mfpbench.yahpo.result import YAHPOResult

_YAHPO_LOADED = False


def _ensure_yahpo_config_set(datapath: Path) -> None:
    """Ensure that the yahpo config is set for this process.

    Will do nothing if it's already set up for this process.

    !!! note "Multiple Simultaneous YAHPO runs"

        When you have multiple runs of YAHPO at once, the will contend for file
        access to the default `settings_path="~/.config/yahpo_gym"`, a yaml file that
        defines where the 'data_path' is. This includes writes which can cause
        processes to crash.

        This `LocalConfiguration` that holds the `settings_path` is created upon import
        of `yahpo_gym` and treated as a Singleton for the process. However the
        reads/writes only happen upon running of a benchmark. Therefore we must disable
        the race condition of multiple processes all trying to access the default.

        There are two methods to address this:

        1. Setting the `YAHPO_LOCAL_CONFIG` environment variable before running the
            script.
        2. Modifying the Singleton before it's usage (this approach).

        Option 1. is likely the intended approach, however we wish to remove this burden
        from the user. Therefore we are taking approach 2.

        This is done by assinging each process a unique id and creating duplicate
        configs in a specially assigned temporary directory.

        The downside of this approach is that it will create junk files in the tmpdir
        which we can not automatically cleanup. These will be located in
        `"tmpdir/yahpo_gym_tmp_configs_delete_me_freely"`.

    Args:
        datapath: The path to the data directory.
    """
    if _YAHPO_LOADED:
        return

    pid = os.getpid()
    uuid_str = str(uuid.uuid4())
    unique_process_id = f"{uuid_str}_{pid}"

    tmpdir = tempfile.gettempdir()
    yahpo_dump_dir = Path(tmpdir) / "yahpo_gym_tmp_configs_delete_me_freely"
    yahpo_dump_dir.mkdir(exist_ok=True)

    config_for_this_process = yahpo_dump_dir / f"config_{unique_process_id}.yaml"

    yahpo_gym.local_config.settings_path = config_for_this_process
    yahpo_gym.local_config.init_config(data_path=str(datapath))
    return


# A Yahpo Benchmark is parametrized by a YAHPOConfig, YAHPOResult and fidelity
C = TypeVar("C", bound=YAHPOConfig)
R = TypeVar("R", bound=YAHPOResult)
F = TypeVar("F", int, float)


class YAHPOBenchmark(Benchmark[C, R, F]):
    yahpo_base_benchmark_name: ClassVar[str]
    """Base name of the yahpo benchmark."""

    yahpo_instances: tuple[str, ...] | None
    """The instances available for this benchmark, if Any."""

    yahpo_task_id_name: ClassVar[str | None]
    """Name of hp used to indicate task."""

    yahpo_forced_remove_hps: Mapping[str, int | float | str] | None
    """Any hyperparameters that should be forcefully deleted from the space
    but have default values filled in"""

    yahpo_replacements_hps: Sequence[tuple[str, str]] | None
    """Any replacements that need to be done in hyperparameters
    [(dataclass_version, dict_version)]"""

    datadir: Path
    """The path to where the data is stored."""

    task_id: str
    """The task id for this benchmark."""

    def __init__(  # noqa: C901
        self,
        task_id: str,
        *,
        datadir: str | Path | None = None,
        seed: int | None = None,
        prior: str | Path | C | Mapping[str, Any] | None = None,
        perturb_prior: float | None = None,
    ):
        """Initialize a Yahpo Benchmark.

        Args:
            task_id: The task id to choose.
            seed: The seed to use
            datadir: The path to where mfpbench stores it data. If left to `None`,
                will use the `_default_download_dir = ./data/yahpo-gym-data`.
            seed: The seed for the benchmark instance
            prior: The prior to use for the benchmark. If None, no prior is used.
                If a str, will check the local location first for a prior
                specific for this benchmark, otherwise assumes it to be a Path.
                If a Path, will load the prior from the path.
                If a Mapping, will be used directly.
            perturb_prior: If given, will perturb the prior by this amount. Only used if
                `prior=` is given as a config.
        """
        # Validation
        cls = self.__class__

        # These errors are maintainers errors, not user errors
        if cls.yahpo_forced_remove_hps is not None and cls.has_conditionals:
            raise NotImplementedError(
                "Error setting up a YAHPO Benchmark with conditionals",
                " and forced hps",
            )

        if cls.yahpo_task_id_name is not None and cls.has_conditionals:
            raise NotImplementedError(
                f"{self.name} has conditionals, can't remove task_id from space",
            )

        instances = cls.yahpo_instances
        if task_id is None and instances is not None:
            raise ValueError(f"{cls} requires a task in {instances}")
        if task_id is not None and instances is None:
            raise ValueError(f"{cls} has no instances, you passed {task_id}")
        if task_id is not None and instances and task_id not in instances:
            raise ValueError(f"{cls} requires a task in {instances}")

        if datadir is None:
            datadir = YAHPOSource.default_location()
        elif isinstance(datadir, str):
            datadir = Path(datadir)

        datadir = Path(datadir) if isinstance(datadir, str) else datadir
        if not datadir.exists():
            raise FileNotFoundError(
                f"Can't find folder at {datadir}, have you run\n"
                f"`python -m mfpbench download --status --data-dir {datadir.parent}`",
            )
        _ensure_yahpo_config_set(datadir)

        bench = yahpo_gym.BenchmarkSet(
            cls.yahpo_base_benchmark_name,
            instance=task_id,
            multithread=False,
        )
        name = f"{cls.yahpo_base_benchmark_name}-{task_id}"

        # These can have one or two fidelities
        # NOTE: seed is allowed to be int | None
        space = bench.get_opt_space(
            drop_fidelity_params=True,
            seed=seed,  # type: ignore
        )

        if cls.yahpo_task_id_name is not None:
            space = remove_hyperparameter(cls.yahpo_task_id_name, space)

        if cls.yahpo_forced_remove_hps is not None:
            names = space.get_hyperparameter_names()
            for key in cls.yahpo_forced_remove_hps:
                if key in names:
                    space = remove_hyperparameter(key, space)

        self._bench = bench
        self.datadir = datadir
        self.task_id = task_id
        super().__init__(
            name=name,
            seed=seed,
            space=space,
            prior=prior,
            perturb_prior=perturb_prior,
        )

    @property
    def bench(self) -> yahpo_gym.BenchmarkSet:
        """The underlying yahpo gym benchmark."""
        if self._bench is None:
            bench = yahpo_gym.BenchmarkSet(
                self.yahpo_base_benchmark_name,
                instance=self.task_id,
                multithread=False,
            )
            self._bench = bench
        return self._bench

    def load(self) -> None:
        """Load the benchmark into memory."""
        _ = self.bench

    @override
    def _objective_function(self, config: C, at: F) -> R:
        query = config.dict()

        if self.yahpo_forced_remove_hps is not None:
            query.update(self.yahpo_forced_remove_hps)

        if self.task_id is not None and self.yahpo_task_id_name is not None:
            query[self.yahpo_task_id_name] = self.task_id

        query[self.fidelity_name] = at

        # NOTE: seed is allowed to be int | None
        results: list[dict] = self.bench.objective_function(
            query,
            seed=self.seed,  # type: ignore
        )
        result = results[0]

        return self.Result.from_dict(
            config=config,
            result=result,
            fidelity=at,
        )

    @override
    def _trajectory(self, config: C, *, frm: F, to: F, step: F) -> list[R]:
        query = config.dict()

        if self.yahpo_forced_remove_hps is not None:
            query.update(self.yahpo_forced_remove_hps)

        if self.task_id is not None and self.yahpo_task_id_name is not None:
            query[self.yahpo_task_id_name] = self.task_id

        # Copy same config and insert fidelities for each
        queries: list[dict] = [
            {**query, self.fidelity_name: f}
            for f in self.iter_fidelities(frm=frm, to=to, step=step)
        ]

        # NOTE: seed is allowed to be int | None
        results: list[dict] = self.bench.objective_function(
            queries,
            seed=self.seed,  # type: ignore
        )

        return [
            self.Result.from_dict(
                config=config,
                result=result,
                fidelity=query[self.fidelity_name],
            )
            # We need to loop over q's for fidelity
            for result, query in zip(results, queries)
        ]