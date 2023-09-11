from __future__ import annotations

from dataclasses import dataclass
from typing_extensions import override

from ConfigSpace import ConfigurationSpace, UniformFloatHyperparameter

from mfpbench.pd1.benchmark import PD1Benchmark, PD1Config, PD1ResultTransformer


@dataclass(frozen=True, eq=False, unsafe_hash=True)
class PD1Config_translatewmt_xformer_64(PD1Config):
    @override
    def validate(self) -> None:
        assert 0.0100221257 <= self.lr_decay_factor <= 0.988565263
        assert 1.00276e-05 <= self.lr_initial <= 9.8422475735
        assert 0.1004250993 <= self.lr_power <= 1.9985927056
        assert 5.86114e-05 <= self.opt_momentum <= 0.9989999746


class PD1translatewmt_xformer_64(PD1Benchmark):
    fidelity_name = "epoch"
    fidelity_range = (1, 19, 1)

    Config = PD1Config_translatewmt_xformer_64
    Result = PD1ResultTransformer

    pd1_dataset = "translate_wmt"
    pd1_model = "xformer_translate"
    pd1_batchsize = 64
    pd1_metrics = ("valid_error_rate", "train_cost")

    @classmethod
    def _create_space(cls, seed: int | None = None) -> ConfigurationSpace:
        cs = ConfigurationSpace(seed=seed)
        cs.add_hyperparameters(
            [
                UniformFloatHyperparameter(
                    "lr_decay_factor",
                    lower=0.0100221257,
                    upper=0.988565263,
                ),
                UniformFloatHyperparameter(
                    "lr_initial",
                    lower=1.00276e-05,
                    upper=9.8422475735,
                    log=True,
                ),
                UniformFloatHyperparameter(
                    "lr_power",
                    lower=0.1004250993,
                    upper=1.9985927056,
                ),
                UniformFloatHyperparameter(
                    "opt_momentum",
                    lower=5.86114e-05,
                    upper=0.9989999746,
                    log=True,
                ),
            ],
        )
        return cs