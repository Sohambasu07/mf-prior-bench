from __future__ import annotations

from typing import Any

import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from ConfigSpace import Configuration
from dehb import DEHB
from sklearn.model_selection import KFold, cross_validate
from xgboost import XGBRegressor

# TODO: Should really move this
from mfpbench.pd1.processing.columns import COLUMNS, DATASET_NAMES
from mfpbench.pd1.surrogate.xgboost_space import MAX_ESTIMATORS, MIN_ESTIMATORS, space

HERE = Path(__file__).absolute().resolve().parent
DATADIR = HERE.parent.parent.parent / "data"


def dehb_target_function(
    config: Configuration,
    budget: int | float | None,
    X: pd.DataFrame,
    y: pd.Series,
    seed: int | None = None,
    default_budget: int = MAX_ESTIMATORS,
    cv: int = 5,
    scoring: tuple[str] = ("r2",),
) -> dict[str, Any]:
    start = time.time()

    # Not sure if this is really needed but it's in example code for dehb
    if budget is None:
        budget = default_budget
    else:
        budget = int(budget)

    model = XGBRegressor(**config, seed=seed, n_estimators=budget)
    scores = cross_validate(
        estimator=model,
        X=X,
        y=y,
        cv=KFold(shuffle=True, random_state=seed, n_splits=cv),
        scoring=scoring,
        return_train_score=True,
    )

    primary_eval_metric = scoring[0]
    primary = np.mean(scores[f"test_{primary_eval_metric}"])
    print(scores)
    print(primary)

    cost = time.time() - start
    for k, v in scores.items():
        scores[k] = list(v) if isinstance(v, np.ndarray) else v

    return {
        "fitness": -primary,  # DEHB minimized
        "cost": cost,
        "info": {
            "score": primary,
            "cv_scores": scores,
            "budget": budget,
            "config": dict(config),
        },
    }


def find_xgboost_surrogate(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    cv: int = 5,
    seed: int | None = None,
    opt_time: float = 30.0,
    output_path: Path | None = None,
    n_workers: int = 1,
) -> XGBRegressor:
    cs = space(seed=seed)
    if output_path is None:
        timestamp = datetime.isoformat(datetime.now())
        output_path = Path(f"surrogate-opt-{y.name}-{timestamp}")

    if not output_path.exists():
        output_path.mkdir(exist_ok=True)

    dehb_path = output_path / "dehb"
    if not dehb_path.exists():
        dehb_path.mkdir(exist_ok=True)

    dehb = DEHB(
        f=dehb_target_function,
        cs=cs,
        dimensions=len(cs.get_hyperparameters()),
        min_budget=MIN_ESTIMATORS,
        max_budget=MAX_ESTIMATORS,
        n_workers=n_workers,
        output_path=str(dehb_path),
    )

    traj, runtime, hist = dehb.run(
        total_cost=opt_time,
        verbose=True,
        save_intermediate=False,
        # kwargs
        X=X,
        y=y,
        cv=cv,
    )

    # Now we find the one with the highest test_score and use that for
    # training our final model
    infos = [info for *_, info in hist]
    best = max(infos, key=lambda i: i["score"])
    print("BEST")
    print("=" * 30)
    print(best)
    print("=" * 30)

    # Write out the info
    info_path = output_path / "info.json"
    best_path = output_path / "best.json"
    with open(info_path, "w") as f:
        json.dump(infos, f)

    with open(best_path, "w") as f:
        json.dump(best, f)

    best_config = best["config"]
    best_budget = best["budget"]

    # Train
    print(f"Training {best_config} for budget {best_budget}")
    model = XGBRegressor(**best_config, seed=seed, n_estimators=best_budget)
    model.fit(X, y)
    return model


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=DATASET_NAMES, required=True, type=str)
    parser.add_argument("--datadir", default=str(DATADIR), type=str)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--cv", type=int, required=True)
    parser.add_argument("--dehb-output", default=".dehb_output", type=str)
    parser.add_argument("--time", type=int, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--y",
        choices=["valid_error_rate", "test_error_rate", "train_cost"],
        required=True,
        type=str,
    )

    args = parser.parse_args()

    pd1dir = Path(args.datadir) / "pd1-data"
    surrogate_dir = pd1dir / "surrogates"
    surrogate_path = surrogate_dir / f"{args.dataset}-{args.y}.json"

    if not surrogate_dir.exists():
        surrogate_dir.mkdir(exist_ok=True)

    datapath = pd1dir / f"{args.dataset}_surrogate.csv"
    df = pd.read_csv(datapath)

    if args.y not in df.columns:
        raise ValueError(f"Can't train for {args.y} for dataset {args.dataset}")

    metrics = [c.rename if c.rename else c.name for c in COLUMNS if c.metric]
    valid_metrics = [m for m in metrics if m in df.columns]

    df = df.dropna()
    X = df.drop(columns=valid_metrics)
    y = df[args.y]

    xgboost_model = find_xgboost_surrogate(
        X=X,
        y=y,
        seed=args.seed,
        output_path=Path(args.dehb_output),
        opt_time=args.time,
        cv=args.cv,
        n_workers=args.workers,
    )

    print(f"Saving model to {surrogate_path}")
    xgboost_model.save_model(surrogate_path)

    # Try load it?
    loaded_model = XGBRegressor()
    loaded_model.load_model(surrogate_path)

    print("Trying to predict")
    y_pred = loaded_model.predict(X)

    print("Success!")
