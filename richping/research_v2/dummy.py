"""Mechanics-only recorder. This is not an investment strategy."""

from .contracts import Decision, JsonObject, StrategyState


class RecorderStrategy:
    strategy_id = "fixture-recorder-v1"
    specification = JsonObject.of({"purpose": "engine-fixture", "version": 1})

    def initialize(self, context):
        if context.bars:
            raise ValueError("Recorder expects an empty initial view")
        return StrategyState("recorder-v1", JsonObject.of({"events": 0}))

    def on_event(self, context, state, event):
        if state.version != "recorder-v1":
            raise ValueError("Unsupported recorder state version")
        return Decision(StrategyState("recorder-v1", JsonObject.of({
            "events": state.data.unpack()["events"] + 1,
            "visible": [{"symbol": b.symbol, "timeframe": b.timeframe,
                         "end_at": b.end_at.isoformat()} for b in context.bars]})))
