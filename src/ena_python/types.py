from __future__ import annotations

from typing import Literal, TypeAlias

ModelType: TypeAlias = Literal["EndPoint", "AccumulatedTrajectory", "SeparateTrajectory"]
WindowType: TypeAlias = Literal["MovingStanzaWindow", "Conversation"]
WeightMode: TypeAlias = Literal["binary", "weighted"]
