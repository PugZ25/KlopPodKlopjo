from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .config import SplitConfig


@dataclass(frozen=True)
class DatasetSplit:
    name: str
    row_indices: list[int]
    unique_times: list[datetime]

    @property
    def row_count(self) -> int:
        return len(self.row_indices)

    @property
    def unique_time_count(self) -> int:
        return len(self.unique_times)

    @property
    def start_time(self) -> str:
        return self.unique_times[0].isoformat(sep=" ")

    @property
    def end_time(self) -> str:
        return self.unique_times[-1].isoformat(sep=" ")


def build_time_splits(
    timestamps: list[datetime],
    split_config: SplitConfig,
) -> dict[str, DatasetSplit]:
    unique_times = sorted(set(timestamps))
    if len(unique_times) < 3:
        raise ValueError(
            "Need at least three unique timestamps for train/validation/test splitting."
        )

    if split_config.train_end_time and split_config.validation_end_time:
        train_times, validation_times, test_times = _build_boundary_time_buckets(
            unique_times=unique_times,
            split_config=split_config,
        )
    else:
        train_count, validation_count, test_count = _allocate_time_buckets(
            total=len(unique_times),
            split_config=split_config,
        )

        train_times = unique_times[:train_count]
        validation_times = unique_times[train_count : train_count + validation_count]
        test_times = unique_times[
            train_count + validation_count : train_count + validation_count + test_count
        ]

    time_to_split = {}
    for time_value in train_times:
        time_to_split[time_value] = "train"
    for time_value in validation_times:
        time_to_split[time_value] = "validation"
    for time_value in test_times:
        time_to_split[time_value] = "test"

    split_rows: dict[str, list[int]] = {"train": [], "validation": [], "test": []}
    for index, timestamp in enumerate(timestamps):
        split_rows[time_to_split[timestamp]].append(index)

    return {
        "train": DatasetSplit("train", split_rows["train"], train_times),
        "validation": DatasetSplit("validation", split_rows["validation"], validation_times),
        "test": DatasetSplit("test", split_rows["test"], test_times),
    }


def _allocate_time_buckets(total: int, split_config: SplitConfig) -> tuple[int, int, int]:
    train_count = max(1, int(total * split_config.train_ratio))
    validation_count = max(1, int(total * split_config.validation_ratio))
    test_count = total - train_count - validation_count

    while test_count < 1:
        if validation_count > 1:
            validation_count -= 1
        elif train_count > 1:
            train_count -= 1
        test_count = total - train_count - validation_count

    if min(train_count, validation_count, test_count) < 1:
        raise ValueError("Unable to allocate at least one time bucket to each split.")

    return train_count, validation_count, test_count


def _build_boundary_time_buckets(
    *,
    unique_times: list[datetime],
    split_config: SplitConfig,
) -> tuple[list[datetime], list[datetime], list[datetime]]:
    train_end_time = _parse_boundary_time(split_config.train_end_time, "split.train_end_time")
    validation_end_time = _parse_boundary_time(
        split_config.validation_end_time,
        "split.validation_end_time",
    )

    if train_end_time >= validation_end_time:
        raise ValueError("split.train_end_time must be earlier than split.validation_end_time.")

    train_times = [time for time in unique_times if time <= train_end_time]
    validation_times = [
        time for time in unique_times if train_end_time < time <= validation_end_time
    ]
    test_times = [time for time in unique_times if time > validation_end_time]

    if not train_times or not validation_times or not test_times:
        raise ValueError(
            "Explicit split boundaries must leave at least one timestamp in train, validation, and test."
        )

    return train_times, validation_times, test_times


def _parse_boundary_time(raw_value: str | None, field_name: str) -> datetime:
    if raw_value is None:
        raise ValueError(f"{field_name} is required.")
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid datetime for {field_name}: {raw_value}") from exc
