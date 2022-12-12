# Copied from https://github.com/automl/jahs_bench_201/blob/c1e92dd92a0c4906575c4e3e4ee9e7420efca5f1/jahs_bench/lib/core/configspace.py#L4  # noqa: 501
# See for why we copy: https://github.com/automl/jahs_bench_201/issues/4
from __future__ import annotations

import ConfigSpace as CS
import numpy as np
from jahs_bench.lib.core.constants import Activations


def jahs_configspace(
    name: str = "jahs_bench_config_space",
    seed: int | np.random.RandomState | None = None,
) -> CS.ConfigurationSpace:
    """The configuration space for all datasets in JAHSBench

    Parameters
    ----------
    name: str = "jahs_bench_config_space"
        The name to give to the config space.

    seed : int | np.random.RandomState | None = None
        The seed to use for the config space

    Returns
    -------
    ConfigurationSpace
    """
    if isinstance(seed, np.random.RandomState):
        seed = seed.tomaxint()

    space = CS.ConfigurationSpace(name=name, seed=seed)
    space.add_hyperparameters(
        [
            CS.Constant(
                "N",
                # sequence=[1, 3, 5],
                value=5,  # This is the value for NB201
                meta=dict(help="Number of cell repetitions"),
            ),
            CS.Constant(
                "W",
                # sequence=[4, 8, 16],
                value=16,  # This is the value for NB201
                meta=dict(
                    help="The width of the first channel in the cell. Each of the "
                    "subsequent cell's first channels is twice as wide as the "
                    "previous cell's, thus, for a value 4 (default) of W, the first "
                    "channel widths are [4, 8, 16]."
                ),
            ),
            CS.CategoricalHyperparameter(
                "Op1",
                choices=list(range(5)),
                default_value=0,
                meta=dict(help="The operation on the first edge of the cell."),
            ),
            CS.CategoricalHyperparameter(
                "Op2",
                choices=list(range(5)),
                default_value=0,
                meta=dict(help="The operation on the second edge of the cell."),
            ),
            CS.CategoricalHyperparameter(
                "Op3",
                choices=list(range(5)),
                default_value=0,
                meta=dict(help="The operation on the third edge of the cell."),
            ),
            CS.CategoricalHyperparameter(
                "Op4",
                choices=list(range(5)),
                default_value=0,
                meta=dict(help="The operation on the fourth edge of the cell."),
            ),
            CS.CategoricalHyperparameter(
                "Op5",
                choices=list(range(5)),
                default_value=0,
                meta=dict(help="The operation on the fifth edge of the cell."),
            ),
            CS.CategoricalHyperparameter(
                "Op6",
                choices=list(range(5)),
                default_value=0,
                meta=dict(help="The operation on the sixth edge of the cell."),
            ),
            # CS.OrdinalHyperparameter(
            #     "Resolution",
            #     sequence=[0.25, 0.5, 1.0],
            #     default_value=1.0,
            #     meta=dict(
            #       help="The sample resolution of the input images w.r.t. one side of"
            #       " the actual image size, assuming square images, i.e. for a dataset"
            #       " with 32x32 images, specifying a value of 0.5 corresponds to using"
            #       " downscaled images of size 16x16 as inputs."
            #     ),
            # ),
            CS.Constant(
                "Resolution",
                value=1.0,
                meta=dict(
                    help="The sample resolution of the input images w.r.t. one side of"
                    " the actual image size, assuming square images, i.e. for a dataset"
                    " with 32x32 images, specifying a value of 0.5 corresponds to using"
                    " downscaled images of size 16x16 as inputs."
                ),
            ),
            CS.CategoricalHyperparameter(
                "TrivialAugment",
                choices=[True, False],
                default_value=False,
                meta=dict(
                    help="Controls whether or not TrivialAugment is used for"
                    " pre-processing data. If False (default), a set of manually chosen"
                    " transforms is applied during pre-processing. If True, these are"
                    " skipped in favor of applying random transforms selected by"
                    " TrivialAugment."
                ),
            ),
            CS.CategoricalHyperparameter(
                "Activation",
                choices=list(Activations.__members__.keys()),
                default_value="ReLU",
                meta=dict(
                    help="Which activation function is to be used for the network."
                    " Default is ReLU."
                ),
            ),
        ]
    )

    # Add Optimizer related HyperParamters
    optimizers = CS.Constant(
        "Optimizer",
        value="SGD",
        meta=dict(
            help="Which optimizer to use for training this model. "
            "This is just a placeholder for now, to be used "
            "properly in future versions."
        ),
    )
    lr = CS.UniformFloatHyperparameter(
        "LearningRate",
        lower=1e-3,
        upper=1e0,
        default_value=1e-1,
        log=True,
        meta=dict(
            help="The learning rate for the optimizer used during model training. In"
            " the case of adaptive learning rate optimizers such as Adam, this is the"
            " initial learning rate."
        ),
    )
    weight_decay = CS.UniformFloatHyperparameter(
        "WeightDecay",
        lower=1e-5,
        upper=1e-2,
        default_value=5e-4,
        log=True,
        meta=dict(
            help="Weight decay to be used by the optimizer during model training."
        ),
    )

    space.add_hyperparameters([optimizers, lr, weight_decay])
    return space
