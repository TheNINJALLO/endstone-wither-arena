"""
Endstone Wither Arena Plugin

This plugin restricts Wither spawning to a designated arena in the Overworld,
prevents Wither explosions from destroying blocks, restricts mob spawning in the arena,
and protects blocks from being broken (except specific items like shulker boxes and gravestones).
"""

from endstone_wither_arena.wither_arena import WitherArenaPlugin

__all__ = ["WitherArenaPlugin"]
__version__ = "2.0.0"