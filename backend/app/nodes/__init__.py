from __future__ import annotations

from app.core.workflow.registry import NodeRegistry
from app.nodes.ai import SelectSegmentsNode, TranscribeNode
from app.nodes.media import (
    BurnSubtitlesNode,
    CutClipNode,
    CutClipsNode,
    ExportVideoNode,
    ExtractAudioNode,
    ProbeMediaNode,
)
from app.nodes.subtitle import BuildSubtitleNode


def register_nodes(registry: NodeRegistry) -> None:
    for node_cls in (
        ProbeMediaNode,
        ExtractAudioNode,
        CutClipNode,
        CutClipsNode,
        ExportVideoNode,
        BurnSubtitlesNode,
        TranscribeNode,
        SelectSegmentsNode,
        BuildSubtitleNode,
    ):
        registry.register(node_cls)
